from __future__ import annotations

import sys
import types

from jarvis_show import voice_chat


def install_fakes(monkeypatch, devices):
    calls = {}
    sd = types.SimpleNamespace(query_devices=lambda: devices, default=types.SimpleNamespace(device=(1, 3)))
    cli = types.ModuleType("openjarvis.cli")
    cli.main = lambda: calls.setdefault("argv", list(sys.argv))
    pkg = types.ModuleType("openjarvis")
    monkeypatch.setitem(sys.modules, "sounddevice", sd)
    monkeypatch.setitem(sys.modules, "openjarvis", pkg)
    monkeypatch.setitem(sys.modules, "openjarvis.cli", cli)
    return sd, calls


DEVICES = [
    {"name": "Speakers", "max_input_channels": 0},
    {"name": "Microphone Array", "max_input_channels": 2},
    {"name": "Headset Mic", "max_input_channels": 1},
]


def test_hands_over_to_the_native_voice_chat_with_the_right_arguments(monkeypatch):
    monkeypatch.delenv("JARVIS_MIC", raising=False)
    sd, calls = install_fakes(monkeypatch, DEVICES)
    assert voice_chat.main() == 0
    assert calls["argv"] == ["jarvis", "chat", "--voice"]
    assert sd.default.device == (1, 3)  # untouched: Windows default microphone


def test_jarvis_mic_selects_the_input_device(monkeypatch):
    monkeypatch.setenv("JARVIS_MIC", "headset")
    sd, calls = install_fakes(monkeypatch, DEVICES)
    assert voice_chat.main() == 0
    assert sd.default.device == (2, 3)


def test_invalid_jarvis_mic_stops_with_a_clear_message(monkeypatch, capsys):
    monkeypatch.setenv("JARVIS_MIC", "webcam")
    sd, calls = install_fakes(monkeypatch, DEVICES)
    assert voice_chat.main() == 2
    assert "argv" not in calls and "--list-devices" in capsys.readouterr().out
