"""Run the CW decoder over a recorded WAV file (e.g. one made with `cwic705 --record`)."""

from __future__ import annotations

import argparse
import wave

import numpy as np

from cwic705.decoder import CwDecoder, find_tone


def load_wav(path: str) -> tuple[np.ndarray, int]:
    with wave.open(path, "rb") as wav:
        if wav.getsampwidth() != 2:
            raise SystemExit("only 16-bit WAV files are supported")
        rate, channels = wav.getframerate(), wav.getnchannels()
        data = np.frombuffer(wav.readframes(wav.getnframes()), "<i2").astype(np.float32) / 32768
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return data, rate


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="cwic705-replay", description=__doc__)
    p.add_argument("wav")
    p.add_argument("--pitch", type=float, default=600, help="CW pitch of the radio (Hz)")
    p.add_argument("--wpm", type=float, default=18, help="initial speed estimate")
    p.add_argument("--no-afc", action="store_true")
    p.add_argument("--stats", action="store_true", help="print decoder state every second")
    args = p.parse_args(argv)

    samples, rate = load_wav(args.wav)
    tone, score = find_tone(samples, rate, 200, 1500)
    print(f"{len(samples) / rate:.1f} s at {rate} Hz; strongest tone {tone or 0:.0f} Hz "
          f"(peak/median {score:.1f})")
    out: list[str] = []
    decoder = CwDecoder(rate, args.pitch, args.wpm, on_text=out.append)
    decoder.afc = not args.no_afc
    for i in range(0, len(samples), rate // 50):
        decoder.process(samples[i:i + rate // 50])
        if args.stats and (i // (rate // 50)) % 50 == 0:
            print(f"[{i / rate:6.1f}s] tone={decoder.tone:.0f} wpm={decoder.wpm:.1f} "
                  f"snr={decoder.snr_db:.1f}dB squelch={'closed' if decoder.squelched else 'open'}"
                  f" | {''.join(out)[-50:]}")
    decoder.process(np.zeros(rate * 2, np.float32))
    print("".join(out).strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
