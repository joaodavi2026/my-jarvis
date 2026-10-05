from __future__ import annotations

import os
import time
from pathlib import Path

from jarvis_show import system


def test_browser_opens_once_per_window_even_across_runs(tmp_path: Path, monkeypatch):
    opened = []
    monkeypatch.setattr(system.webbrowser, "open", lambda url: opened.append(url))
    marker = tmp_path / "stamp"
    assert system.open_browser("http://127.0.0.1:8000", window_s=60, marker=marker) is True
    assert system.open_browser("http://127.0.0.1:8000", window_s=60, marker=marker) is False
    old = time.time() - 120
    os.utime(marker, (old, old))  # the previous activation was long ago
    assert system.open_browser("http://127.0.0.1:8000", window_s=60, marker=marker) is True
    assert len(opened) == 2
