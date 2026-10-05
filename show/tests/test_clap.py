from __future__ import annotations

import numpy as np
import pytest

from jarvis_show.clap import (BLOCK, ClapActivation, ClapConfig, ClapDetector, DoubleClapConfig,
                              DoubleClapMatcher, SAMPLE_RATE)

from .synth import add, blocks, clap, loud_noise, silence, speech_like, thump


def claps_found(stream: np.ndarray, config: ClapConfig | None = None) -> list[float]:
    det = ClapDetector(config)
    found = []
    for i, block in enumerate(blocks(stream)):
        if det.process(block):
            found.append(round(i * BLOCK / SAMPLE_RATE - det.cfg.decay_blocks * BLOCK / SAMPLE_RATE, 2))
    return found


def activations(stream: np.ndarray, config: ClapConfig | None = None, matcher: DoubleClapMatcher | None = None) -> int:
    pipe = ClapActivation(ClapDetector(config), matcher)
    return sum(1 for block in blocks(stream) if pipe.process(block))


def test_a_clap_is_detected_near_its_onset():
    s = silence(3.0)
    add(s, clap(), 1.50)
    found = claps_found(s)
    assert len(found) == 1 and abs(found[0] - 1.50) < 0.06


def test_silence_and_quiet_room_noise_never_trigger():
    assert claps_found(silence(5.0)) == []
    assert claps_found(silence(5.0, level=0.01, seed=3)) == []


def test_speech_like_sound_is_rejected():
    s = silence(4.0)
    add(s, speech_like(0.8), 1.0)
    add(s, speech_like(0.8), 2.4)
    assert claps_found(s) == []


def test_low_frequency_thump_is_rejected():
    s = silence(3.0)
    add(s, thump(), 1.2)
    assert claps_found(s) == []


def test_sustained_loud_noise_is_rejected_and_does_not_poison_detection():
    s = silence(6.0)
    add(s, loud_noise(1.5), 1.0)
    add(s, clap(), 4.0)
    found = claps_found(s)
    assert len(found) == 1 and abs(found[0] - 4.0) < 0.06


def test_sensitivity_higher_thresh_is_less_sensitive():
    s = silence(3.0)
    add(s, clap(amplitude=0.12), 1.5)
    assert len(claps_found(s, ClapConfig(thresh=8.0))) == 1
    assert claps_found(s, ClapConfig(thresh=300.0)) == []


def test_two_claps_in_the_window_activate_once():
    s = silence(4.0)
    add(s, clap(seed=1), 1.0)
    add(s, clap(seed=2), 1.45)
    assert activations(s) == 1


def test_a_single_clap_never_activates():
    s = silence(4.0)
    add(s, clap(), 1.0)
    assert activations(s) == 0


def test_second_clap_too_late_does_not_activate_but_starts_a_new_window():
    s = silence(6.0)
    add(s, clap(seed=1), 1.0)
    add(s, clap(seed=2), 2.5)  # 1.5 s later: outside the 0.8 s window
    assert activations(s) == 0
    add(s, clap(seed=3), 2.9)  # 0.4 s after the previous one: now it is a valid pair
    assert activations(s) == 1


def test_cooldown_prevents_repeated_activation():
    s = silence(8.0)
    for i, t in enumerate([1.0, 1.4, 1.9, 2.3, 2.8, 3.2]):
        add(s, clap(seed=10 + i), t)
    assert activations(s) == 1


def test_after_cooldown_a_new_pair_activates_again():
    s = silence(14.0)
    for i, t in enumerate([1.0, 1.4, 8.0, 8.4]):
        add(s, clap(seed=20 + i), t)
    assert activations(s) == 2


def test_normal_ambient_scenes_do_not_trigger_repeatedly():
    s = silence(10.0, level=0.006, seed=7)
    add(s, speech_like(1.0), 1.0)
    add(s, speech_like(1.0), 3.0)
    add(s, thump(0.3), 5.0)
    add(s, loud_noise(0.8, 0.15), 6.5)
    assert activations(s) == 0


class TestMatcher:
    def test_window_edges(self):
        m = DoubleClapMatcher(DoubleClapConfig(min_gap=0.15, max_gap=0.8, cooldown=2.0))
        assert not m.feed(1.0)
        assert not m.feed(1.1)  # same acoustic event
        assert m.feed(1.5)

    def test_cooldown_blocks_then_releases(self):
        m = DoubleClapMatcher(DoubleClapConfig(cooldown=3.0))
        m.feed(0.0)
        assert m.feed(0.4)
        assert not m.feed(1.0) and not m.feed(1.4)
        m.feed(4.0)
        assert m.feed(4.4)

    def test_reset(self):
        m = DoubleClapMatcher()
        m.feed(0.0)
        m.reset()
        assert not m.feed(0.4)
