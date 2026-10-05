"""Local clap detection. Pure signal processing on small audio blocks; nothing is stored or sent anywhere.

A clap is an impulsive, broadband, short event. A block is accepted as a clap onset when:
  * its peak is well above the (adaptive) background noise floor,
  * it is impulsive (high crest factor) and broadband (high-frequency energy ratio), unlike speech and thumps,
  * the energy decays quickly afterwards (speech, music and sustained noise stay loud and are rejected).
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import numpy as np

SAMPLE_RATE = 16_000
BLOCK = 320  # 20 ms at 16 kHz


@dataclass(frozen=True)
class ClapConfig:
    thresh: float = 8.0  # peak must exceed thresh x noise floor. Higher = LESS sensitive.
    min_peak: float = 0.04  # absolute floor so a silent room does not trigger on tiny clicks
    min_crest: float = 2.2  # peak / rms inside the block (impulsiveness)
    min_hf_ratio: float = 0.12  # energy of the first difference relative to the signal (broadband vs low-frequency)
    decay_blocks: int = 5  # the event must have decayed within ~100 ms
    decay_ratio: float = 0.45  # ... to below this fraction of the onset RMS
    refractory_blocks: int = 5  # ignore onsets right after an event (100 ms)
    warmup_blocks: int = 25  # 0.5 s to learn the noise floor before detecting
    noise_alpha: float = 0.02


class ClapDetector:
    """Feed consecutive mono float32 blocks (BLOCK samples). `process` returns True when a clap is confirmed."""

    def __init__(self, config: ClapConfig | None = None) -> None:
        self.cfg = config or ClapConfig()
        self.noise = 0.0
        self._seen = 0
        self._pending: tuple[float, float] | None = None  # (onset rms, onset peak)
        self._pending_age = 0
        self._tail_rms: list[float] = []
        self._refractory = 0

    @staticmethod
    def _features(block: np.ndarray) -> tuple[float, float, float, float]:
        energy = float(np.mean(block * block))
        rms = energy**0.5
        peak = float(np.max(np.abs(block)))
        diff = np.diff(block)
        hf = float(np.mean(diff * diff)) / (4.0 * energy) if energy > 1e-12 else 0.0
        crest = peak / rms if rms > 1e-9 else 0.0
        return rms, peak, crest, hf

    def process(self, block: np.ndarray) -> bool:
        rms, peak, crest, hf = self._features(np.asarray(block, dtype=np.float32))
        self._seen += 1
        loud = peak >= max(self.cfg.min_peak, self.cfg.thresh * max(self.noise, 1e-5))
        if self._pending is None and not loud or self._seen <= self.cfg.warmup_blocks:
            # Learn the background only from non-event blocks; keep it from chasing sustained loud sounds.
            if self._seen <= self.cfg.warmup_blocks:
                self.noise = rms if self.noise == 0.0 else (1 - 0.1) * self.noise + 0.1 * rms
            elif rms < max(self.noise * 2.0, 1e-5):
                self.noise = (1 - self.cfg.noise_alpha) * self.noise + self.cfg.noise_alpha * rms
        if self._seen <= self.cfg.warmup_blocks:
            return False
        if self._refractory > 0:
            self._refractory -= 1
            return False
        if self._pending is not None:
            return self._advance_candidate(rms)
        if loud and crest >= self.cfg.min_crest and hf >= self.cfg.min_hf_ratio:
            self._pending = (rms, peak)
            self._pending_age = 0
            self._tail_rms = []
        return False

    def _advance_candidate(self, rms: float) -> bool:
        assert self._pending is not None
        self._pending_age += 1
        self._tail_rms.append(rms)
        if self._pending_age < self.cfg.decay_blocks:
            return False
        onset_rms, _ = self._pending
        decayed = max(self._tail_rms[-2:]) < self.cfg.decay_ratio * onset_rms
        self._pending = None
        self._refractory = self.cfg.refractory_blocks
        return decayed


@dataclass(frozen=True)
class DoubleClapConfig:
    min_gap: float = 0.15  # seconds; closer than this is the same clap (echo), not a second one
    max_gap: float = 0.80  # seconds; later than this the first clap is forgotten
    cooldown: float = 5.0  # seconds after an activation during which nothing fires


class DoubleClapMatcher:
    """Turns clap timestamps into activations: needs two claps inside the window; one clap never activates."""

    def __init__(self, config: DoubleClapConfig | None = None) -> None:
        self.cfg = config or DoubleClapConfig()
        self._first: float | None = None
        self._last_fire = -1e9

    def feed(self, t: float) -> bool:
        if t - self._last_fire < self.cfg.cooldown:
            return False
        if self._first is None:
            self._first = t
            return False
        gap = t - self._first
        if gap < self.cfg.min_gap:
            return False  # same acoustic event
        if gap <= self.cfg.max_gap:
            self._first = None
            self._last_fire = t
            return True
        self._first = t  # too late: this clap starts a new window
        return False

    def reset(self) -> None:
        self._first = None


class ClapActivation:
    """Block stream -> activation events (True), with timing derived from the number of samples consumed."""

    def __init__(self, detector: ClapDetector | None = None, matcher: DoubleClapMatcher | None = None) -> None:
        self.detector = detector or ClapDetector()
        self.matcher = matcher or DoubleClapMatcher()
        self._blocks = 0
        self.history: deque[float] = deque(maxlen=8)

    def process(self, block: np.ndarray) -> bool:
        now = self._blocks * BLOCK / SAMPLE_RATE
        self._blocks += 1
        if not self.detector.process(block):
            return False
        # A confirmed clap is reported decay_blocks after its onset; use the onset time.
        onset = now - self.detector.cfg.decay_blocks * BLOCK / SAMPLE_RATE
        self.history.append(onset)
        return self.matcher.feed(onset)
