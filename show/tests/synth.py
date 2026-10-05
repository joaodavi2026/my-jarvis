"""Synthetic audio for detector tests (deterministic, no microphone needed)."""

from __future__ import annotations

import numpy as np

from jarvis_show.clap import BLOCK, SAMPLE_RATE


def silence(seconds: float, level: float = 0.003, seed: int = 0) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(0.0, level, int(seconds * SAMPLE_RATE)).astype(np.float32)


def add(stream: np.ndarray, event: np.ndarray, at_seconds: float) -> None:
    start = int(at_seconds * SAMPLE_RATE)
    end = min(len(stream), start + len(event))
    stream[start:end] += event[: end - start]


def clap(amplitude: float = 0.6, seed: int = 1) -> np.ndarray:
    """Broadband burst, about 30 ms, exponential decay (tau 6 ms)."""
    rng = np.random.default_rng(seed)
    n = int(0.030 * SAMPLE_RATE)
    t = np.arange(n) / SAMPLE_RATE
    return (amplitude * rng.normal(0, 1, n) * np.exp(-t / 0.006)).astype(np.float32)


def speech_like(seconds: float = 0.6, amplitude: float = 0.3) -> np.ndarray:
    """Voiced sound: harmonics of 140 Hz with a syllable-rate envelope. Sustained, mostly low frequency."""
    t = np.arange(int(seconds * SAMPLE_RATE)) / SAMPLE_RATE
    sig = sum(np.sin(2 * np.pi * 140 * k * t) / k for k in range(1, 6))
    env = 0.6 + 0.4 * np.sin(2 * np.pi * 4 * t)
    return (amplitude * env * sig / 2).astype(np.float32)


def thump(amplitude: float = 0.6) -> np.ndarray:
    """Low-frequency knock (table bump): 70 Hz, decays over about 100 ms."""
    t = np.arange(int(0.2 * SAMPLE_RATE)) / SAMPLE_RATE
    return (amplitude * np.sin(2 * np.pi * 70 * t) * np.exp(-t / 0.04)).astype(np.float32)


def loud_noise(seconds: float = 1.0, amplitude: float = 0.25, seed: int = 5) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return (amplitude * rng.normal(0, 1, int(seconds * SAMPLE_RATE))).astype(np.float32)


def blocks(stream: np.ndarray):
    for i in range(0, len(stream) - BLOCK + 1, BLOCK):
        yield stream[i : i + BLOCK]
