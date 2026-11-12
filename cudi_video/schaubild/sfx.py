"""Kleine, selbst erzeugte Soundeffekte (kein Download): Wusch, Pop, Tick, Stift. Leise unter der Stimme (≈ −12 dB),
abschaltbar mit `CUDI_SFX=0`."""

from __future__ import annotations

import os

import numpy as np

GAIN = 0.25                               # relativ zum Stimmpegel ≈ −12 dB


def enabled() -> bool:
    return os.environ.get("CUDI_SFX", "1") != "0"


def _env(n: int, attack: float, rate: int) -> np.ndarray:
    a = max(1, int(attack * rate))
    e = np.exp(-np.linspace(0, 5, n))
    e[:a] *= np.linspace(0, 1, a)
    return e


def make(name: str, rate: int) -> np.ndarray:
    rng = np.random.default_rng(3)
    if name == "wusch":
        n = int(.34 * rate)
        noise = rng.normal(0, 1, n)
        k = np.linspace(40, 4, n).astype(int)                     # gleitender Mittelwert wird kürzer -> Rauschen wird heller
        c = np.cumsum(np.concatenate([[0.0], noise]))
        idx = np.arange(n)
        out = (c[idx + 1] - c[np.maximum(0, idx + 1 - k)]) / k
        out *= np.sin(np.linspace(0, np.pi, n)) ** 2
    elif name == "pop":
        n = int(.09 * rate)
        f = np.linspace(880, 480, n)
        out = np.sin(2 * np.pi * np.cumsum(f) / rate) * _env(n, .003, rate)
    elif name == "tick":
        n = int(.05 * rate)
        out = np.sin(2 * np.pi * 1900 * np.arange(n) / rate) * _env(n, .001, rate)
    else:                                                         # stift: kurze Kratz-Schübe
        n = int(.9 * rate)
        out = rng.normal(0, 1, n) * (np.sin(np.linspace(0, 14 * np.pi, n)) > .2) * np.linspace(1, .3, n)
        out = np.diff(out, prepend=0.0) * .5
    peak = np.abs(out).max() or 1.0
    return (out / peak).astype(np.float32)


def place(track: np.ndarray, events: list[tuple[float, str]], voice_level: float, rate: int) -> None:
    cache: dict[str, np.ndarray] = {}
    for when, name in events:
        clip = cache.setdefault(name, make(name, rate))
        s = int(max(0.0, when) * rate)
        e = min(len(track), s + len(clip))
        if e > s:
            track[s:e] += clip[: e - s] * voice_level * GAIN * (1.6 if name == "wusch" else 1.0)
