"""Volume identity: volumes are recognised by GUID, never by drive letter alone."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

_GUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")


def normalize_guid(value: str) -> str:
    """Accepts a volume path, a braced GUID or a bare GUID; returns the lowercase bare GUID."""
    match = _GUID_RE.search(value)
    if not match:
        raise ValueError("not a volume GUID")
    return match.group(0).lower()


@dataclass(frozen=True)
class VolumeInfo:
    guid: str
    label: str
    filesystem: str
    mount_path: Path | None  # drive root such as D:\ ; None when the volume has no letter
    total_bytes: int
    free_bytes: int
    read_only: bool = False
    media_type: str = "UNKNOWN"  # HDD | SSD | UNKNOWN
    letter: str | None = None  # e.g. D: ; informational, never used for identity

    @property
    def drive_letter(self) -> str | None:
        return self.letter.upper() if self.letter else None


class VolumeProvider(Protocol):
    """Lists the volumes currently mounted. Real implementation: Windows API; tests: fakes."""

    def list_volumes(self) -> list[VolumeInfo]: ...
