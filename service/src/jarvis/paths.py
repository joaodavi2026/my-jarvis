"""Resolution of the internal (SSD) root. The external root comes from StorageManager, never from here."""

from __future__ import annotations

import os
from pathlib import Path


def default_internal_root() -> Path:
    override = os.environ.get("JARVIS_INTERNAL_ROOT")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "JARVIS"
