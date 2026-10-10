"""End-to-end tests against the simulated radio (run in real time, a few seconds each)."""

import asyncio

from cwic705.config import Config
from cwic705.session import Session
from cwic705.transport.sim import SimStation, SimTransport


class RecordingUi:
    def __init__(self):
        self.rx, self.tx, self.infos, self.errors = [], [], [], []

    def rx_text(self, text):
        self.rx.append(text)

    def tx_text(self, text):
        self.tx.append(text)

    def info(self, msgid, **args):
        self.infos.append(msgid.format(**args) if args else msgid)

    def error(self, msgid, **args):
        self.errors.append(msgid.format(**args) if args else msgid)

    def status_changed(self):
        pass


async def _session(transport, tx_enabled=False):
    ui = RecordingUi()
    session = Session(transport, Config(callsign="EA4TST", wpm=30, tx_enabled=tx_enabled), ui)
    await session.start()
    return session, ui


def test_tune_decode_and_transmit():
    async def scenario():
        sim = SimTransport(stations=[SimStation(7_012_000, "CQ DE EA4SIM K", 25, 0.3, pause=0.5)],
                           seed=1)
        session, ui = await _session(sim, tx_enabled=True)
        try:
            await session.execute("/f 7.012")
            await asyncio.sleep(5)
            assert "DE EA4SIM" in "".join(ui.rx)
            await session.execute("/wpm 30")
            await session.execute("cq de {call} <ar>")
            await session.execute("/wait")
            assert sim.sent_text == ["CQ DE EA4TST +"]
            assert ui.tx == ["CQ DE EA4TST +"]
            assert not ui.errors
        finally:
            await session.stop()

    asyncio.run(scenario())


def test_scan_finds_station_skips_carrier_and_learns_sideband():
    async def scenario():
        stations = [SimStation(7_004_000, None, amplitude=0.2),                     # birdie
                    SimStation(7_006_330, "CQ CQ DE EA4SIM K", 22, 0.2, pause=0.3)]
        sim = SimTransport(stations=stations, sideband_sign=-1, frequency=7_000_000, seed=2)
        session, ui = await _session(sim)
        session.scanner.dwell = 1.0
        try:
            await session.execute("/f 7.000")
            session.start_scan(1)
            await asyncio.wait_for(session._scan_task, 30)
            assert abs(sim.frequency - 7_006_330) <= 30, sim.frequency
            assert session.scanner.sideband_sign == -1
            assert sim.filter_index == 9  # filter restored to 500 Hz after the search
            assert any("signal found" in i for i in ui.infos)
        finally:
            await session.stop()

    asyncio.run(scenario())


def test_receive_only_never_keys_the_radio():
    async def scenario():
        sim = SimTransport(stations=[], seed=3)
        sent = []
        original = sim.send_civ
        sim.send_civ = lambda frame: (sent.append(frame), original(frame))
        session, ui = await _session(sim)
        try:
            await session.execute("CQ CQ DE EA4TST")
            await session.execute("/raw 17 41 42")   # send CW
            await session.execute("/raw 1c 00 01")   # PTT on
            session.send_macro("F2")
            await asyncio.sleep(0.3)
            assert sim.sent_text == []
            assert not any(f[4] in (0x17, 0x1C) for f in sent)
            assert not any(f[4:6] == b"\x16\x47" for f in sent)  # break-in left untouched
            assert len(ui.errors) == 4
        finally:
            await session.stop()

    asyncio.run(scenario())
