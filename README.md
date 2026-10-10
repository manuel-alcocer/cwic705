# cwic705

CW (Morse) decoder, skimmer and keyer for the **Icom IC-705**, connected over WiFi using the
radio's built-in network server (the protocol used by RS-BA1/wfview). USB connection is planned
for the next version.

* Connects to the radio, tunes band and frequency, sets CW mode.
* Decodes CW from the receive audio with a **probabilistic (Bayesian) decoder**: timing
  likelihoods tolerant of a human fist plus a CW language model (abbreviations, Q codes,
  reports, MASTER.SCP callsigns). The classic threshold decoder remains available.
* **Translation** of each transmission into plain language (who calls whom, report, name,
  location, goodbye...), with callsign countries and a glossary of CW abbreviations.
* **Channels**: every tuned conversation and every validated skimmer station becomes a channel
  with its transcript, plain-language summaries and statistics (words, recognised %, noise %,
  unreadable characters, callsigns, speed, SNR). F11 lists them; on exit the client offers to
  archive them. Archive: SQLite by default or PostgreSQL (`[channels] database = "postgresql+
  psycopg://..."`, `pip install cwic705[postgres]`), with optional lossless FLAC audio whose
  metadata carries frequency, callsign and start time (`/play` reads them).
* **Recordings**: `--record` saves audio plus a `.json` with the dial frequency; `/play file`
  or `--wav file` decodes a recording exactly as if it came from the radio.
* **Skimmer** (`/skim`, F10): opens the filter to 3.6 kHz, finds every keyed signal and decodes
  them all at once, listing stations by validated callsign (repeated, or known in MASTER.SCP).
* Automatic search (`/scan`) through a band's CW segment; centres the first signal found.
* Sends CW through the radio's internal keyer, with F-key macros.
* **Receive-only by default**: nothing that can key the transmitter is sent unless the core is
  started with `--tx` (or `tx_enabled = true`). No client command can enable it.
* Client/server: the core can run on another machine (e.g. a Raspberry Pi next to the radio).
* Interface in English with translations (Spanish included).

## Architecture

```
            ┌──────────────────────── core (cwic705.core) ───────────────────────┐
 IC-705 ◄──►│ transport (WiFi/USB/sim) · Radio (CI-V) · decoder · skimmer · scan │
            └───────────────┬────────────────────────────────────────────────────┘
                            │ events (JSON)  ▲ command lines ("/f 7.030", "CQ DE ...")
              ┌─────────────┴────────┐  ┌────┴──────────────────────────┐
              │ LocalLink (in-process)│  │ WebSocket server (--serve)     │
              └─────────────┬────────┘  └────┬──────────────────────────┘
                            │                │  RemoteLink (--connect)
                  Textual / plain clients    Textual, plain, future web/Qt clients
```

The protocol is documented at the top of `src/cwic705/core.py`: clients receive `welcome`,
`state`, `skim`, `rx`, `tx`, `info` and `error` events and send command lines. Messages are an
English template plus arguments (`msgid`, `args`) so every client shows them in its own language.

## Radio setup (IC-705)

1. MENU > SET > WLAN Set: connect the radio to your WiFi (or use its access point mode).
2. WLAN Set > Remote Settings: set **Network User1** ID and password; network control **ON**.
3. Note the radio IP address (WLAN Set > Connection Status).

## Install and run

```sh
uv sync
uv run cwic705 --init-config          # writes ~/.config/cwic705/config.toml (edit it)
uv run cwic705 --update-scp           # downloads MASTER.SCP for the skimmer
uv run cwic705                        # full-screen client with the core in-process
uv run cwic705 --sim                  # try it without a radio
uv run cwic705 --plain                # line mode (stdin commands, stdout text)
uv run cwic705 --lang es              # Spanish interface (or [ui] language / CWIC705_LANG)
uv run cwic705 --tx                   # enable transmission (check SWR first!)
```

### Core on a Raspberry Pi, client here

```sh
# on the Pi (next to the radio); token from [server] in its config
uv run cwic705 --serve                       # listens on [server] listen, default 0.0.0.0:7373
# on the desktop
uv run cwic705 --connect rpi.local           # token from [client] token, or --token
```

A server reachable from the network refuses to start without a token. Logs:
`~/.local/state/cwic705/cwic705.log` (`--debug`, `--debug -v` for packet dumps).

## Commands

| Command | Action |
|---|---|
| text + Enter | send in CW (only with `--tx`); prosigns `<AR> <BT> <KN> <SK>` |
| `/f 7.030` · `/f 7030.5` | tune (MHz, kHz or Hz) |
| `/b 40` | go to a band (CW calling frequency) |
| `/up 500` · `/down` · PgUp/PgDn | move the dial |
| `/skim` · F10 · `/go N` | skimmer on/off · tune station N (or ↑↓ + Enter) |
| `/scan [up\|down] [band]` · `/next` · `/prev` | automatic search |
| `/stop` · Esc | stop search / transmission |
| `/wpm 22` · `/pitch 600` · `/power 50` · `/filter 500` | radio settings |
| `/afc on\|off` · `/rxwpm 25` | decoder settings |
| `/call EA4XXX` · `/macros` · `/macro F2` · F2–F9 | macros |
| `/play file.wav [MHz] [x4]` · `/play stop` | decode a recording as if it came from the radio |
| F11 · `/channels` | channels of the session and the archive (save, tune, play) |
| `/raw 03` | raw CI-V command (debugging) |
| `/help` · `/clear` · `/quit` | |

## Decoder benchmark

`python -m cwic705.bench` decodes synthetic QSOs with known text (human fist, fading, static
crashes, SNR sweep) and prints the character error rate of each decoder. On a typical run:

| SNR (500 Hz) | classic | bayes |
|---|---|---|
| 20 dB | 7 % | 2–3 % |
| 8 dB | 12 % | 5 % |
| 3 dB | 37 % | 27–30 % |

`cwic705-replay file.wav [--skim]` runs a recording through the decoder or the skimmer.
Choose the decoder with `[decoder] engine = "bayes" | "classic"`.

## Translations

Strings are English in the code, wrapped in `_()` / `N_()` (`src/cwic705/i18n.py`). Catalogs are
plain gettext `.po` files in `src/cwic705/locales/<lang>/`, read directly (no compile step). The
test suite fails if a marked string has no Spanish translation or its `{placeholders}` differ.

## Layout

```
src/cwic705/
  core.py            core + event protocol      server.py  WebSocket server
  links.py           LocalLink / RemoteLink     session.py commands, TX queue, reconnect
  transport/lan.py   Icom network protocol      transport/sim.py  simulated IC-705
  radio.py           CI-V commands              decoder.py  CW decoder + signal detector
  skimmer.py         multi-signal skimmer       scanner.py  automatic search
  bayes.py           probabilistic decoder      bench.py    decoder benchmark
  interpret.py       plain-language translation hamdata.py  countries, Q codes (from HAMRLOG)
  playback.py        WAV/FLAC playback          channels.py channels, statistics, archive
  screens.py         dialogs, channels view
  tui.py styles.tcss Textual client (HAMRLOG look)   plain.py  line client
  i18n.py locales/   translations
```

## Troubleshooting

* **Does not connect after the program was killed or WiFi dropped**: the radio keeps the old
  session for about a minute and ignores new connections meanwhile. cwic705 waits and retries
  on its own (up to 90 s). Quitting normally (`/quit`, Ctrl-Q) logs out cleanly.
* Packet dumps for bug reports: `cwic705 --debug -v`.

Tests: `uv run pytest` (fake Icom network server, simulator end-to-end, client/server, i18n).
