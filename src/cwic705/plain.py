"""Line-oriented client: decoded text on stdout, commands/text read from stdin.

Useful over SSH without a full terminal, for logging, or for scripting.
"""

from __future__ import annotations

import asyncio
import sys

from cwic705.i18n import render
from cwic705.links import Link


class PlainClient:
    def __init__(self, link: Link, quit_event: asyncio.Event) -> None:
        self.link = link
        self.quit_event = quit_event
        self._at_line_start = True
        self._transmitting = False
        link.on_event = self._on_event

    def _line(self, text: str) -> None:
        if not self._at_line_start:
            sys.stdout.write("\n")
        sys.stdout.write(text + "\n")
        sys.stdout.flush()
        self._at_line_start = True

    def _on_event(self, event: dict) -> None:
        kind = event.get("type")
        if kind == "state":
            self._transmitting = event.get("transmitting", False)
        elif kind == "rx":
            sys.stdout.write(event["text"])
            sys.stdout.flush()
            self._at_line_start = False
        elif kind == "tx":
            self._line(f"TX> {event['text']}")
        elif kind == "info":
            self._line(f"-- {render(event)}")
        elif kind == "error":
            self._line(f"!! {render(event)}")

    async def run(self) -> None:
        loop = asyncio.get_running_loop()
        lines: asyncio.Queue[str | None] = asyncio.Queue()

        def on_stdin() -> None:
            line = sys.stdin.readline()
            lines.put_nowait(line if line else None)

        loop.add_reader(sys.stdin.fileno(), on_stdin)
        stop = asyncio.create_task(self._stopped())
        try:
            while True:
                get = asyncio.create_task(lines.get())
                done, _ = await asyncio.wait({get, stop}, return_when=asyncio.FIRST_COMPLETED)
                if get not in done:
                    get.cancel()
                    break
                line = get.result()
                if line is None:  # EOF: keep receiving until Ctrl-C
                    loop.remove_reader(sys.stdin.fileno())
                    await stop
                    break
                if line.strip().lower() in ("/quit", "/q", "/exit"):
                    break
                if line.strip().lower().startswith("/wait"):
                    await self._wait(line.split()[1:])  # scripting aid, also works remotely
                    continue
                await self.link.command(line.strip())
        finally:
            stop.cancel()
            loop.remove_reader(sys.stdin.fileno())

    async def _wait(self, args: list[str]) -> None:
        """/wait N pauses N seconds; /wait alone waits until the transmission ends."""
        if args:
            await asyncio.sleep(float(args[0]))
            return
        await asyncio.sleep(1.0)  # let the server start the transmission
        while self._transmitting:
            await asyncio.sleep(0.2)

    async def _stopped(self) -> None:
        quit_wait = asyncio.create_task(self.quit_event.wait())
        closed_wait = asyncio.create_task(self.link.closed.wait())
        await asyncio.wait({quit_wait, closed_wait}, return_when=asyncio.FIRST_COMPLETED)
        quit_wait.cancel()
        closed_wait.cancel()
