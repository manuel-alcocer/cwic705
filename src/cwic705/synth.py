"""Synthetic CW audio, used by the simulator and the tests."""

from __future__ import annotations

import numpy as np

from cwic705 import morse


def keying_envelope(text: str, wpm: float, sample_rate: int, rise: float = 0.005) -> np.ndarray:
    """0..1 keying envelope for `text` with raised-cosine edges."""
    dit = max(1, int(round(morse.dit_seconds(wpm) * sample_rate)))
    segments = morse.elements(text)
    if not segments:
        return np.zeros(0, dtype=np.float32)
    env = np.concatenate([np.full(units * dit, 1.0 if down else 0.0) for down, units in segments])
    n = max(1, int(rise * sample_rate))
    kernel = np.hanning(2 * n + 1)
    env = np.convolve(env, kernel / kernel.sum(), mode="same")
    return env.astype(np.float32)


def cw_signal(text: str, wpm: float, freq: float, sample_rate: int, amplitude: float = 0.5,
              lead: float = 0.3, tail: float = 0.6) -> np.ndarray:
    env = keying_envelope(text, wpm, sample_rate)
    env = np.concatenate([np.zeros(int(lead * sample_rate), np.float32), env,
                          np.zeros(int(tail * sample_rate), np.float32)])
    t = np.arange(len(env)) / sample_rate
    return (amplitude * env * np.sin(2 * np.pi * freq * t)).astype(np.float32)


def noise(n: int, rms: float, rng: np.random.Generator | None = None) -> np.ndarray:
    rng = rng or np.random.default_rng()
    return (rng.standard_normal(n) * rms).astype(np.float32)
