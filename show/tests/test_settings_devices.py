from __future__ import annotations

from pathlib import Path

import pytest

from jarvis_show.devices import resolve_device
from jarvis_show.settings import DEFAULT_THRESH, Settings, find_jingle

DEVICES = [
    {"name": "Speakers (Realtek)", "max_input_channels": 0},
    {"name": "Microphone Array (Realtek)", "max_input_channels": 2},
    {"name": "Headset Mic (USB)", "max_input_channels": 1},
]


def test_default_device_when_not_set():
    assert resolve_device(None, DEVICES) is None and resolve_device("", DEVICES) is None


def test_select_by_index_and_name():
    assert resolve_device("2", DEVICES) == 2
    assert resolve_device("headset", DEVICES) == 2
    assert resolve_device("ARRAY", DEVICES) == 1


@pytest.mark.parametrize("bad", ["0", "9", "webcam"])
def test_invalid_devices_raise_clear_errors(bad):
    with pytest.raises(ValueError):
        resolve_device(bad, DEVICES)


def test_settings_defaults_and_overrides(tmp_path: Path):
    s = Settings.from_env({}, show_dir=tmp_path / "my-jarvis" / "show")
    assert s.clap_thresh == DEFAULT_THRESH and s.mic is None and s.jingle is None
    assert s.openjarvis_dir == tmp_path / "jarvis"
    other = {"JARVIS_CLAP_THRESH": "12.5", "JARVIS_MIC": " usb ", "JARVIS_OPENJARVIS_DIR": "X:/oj"}
    s = Settings.from_env(other, show_dir=tmp_path)
    assert s.clap_thresh == 12.5 and s.mic == "usb" and s.openjarvis_dir == Path("X:/oj")


@pytest.mark.parametrize("value", ["abc", "-3", "0", ""])
def test_bad_threshold_falls_back_to_the_default(value):
    assert Settings.from_env({"JARVIS_CLAP_THRESH": value}, show_dir=Path(".")).clap_thresh == DEFAULT_THRESH


def test_existing_user_jingle_is_found_and_never_touched(tmp_path: Path):
    show = tmp_path / "show"
    (show / "assets").mkdir(parents=True)
    jingle = show / "assets" / "jingle.mp3"
    jingle.write_bytes(b"user media")
    assert find_jingle(None, show) == jingle
    assert jingle.read_bytes() == b"user media"
    assert find_jingle(None, tmp_path / "empty") is None
    assert find_jingle(str(jingle), tmp_path / "empty") == jingle
