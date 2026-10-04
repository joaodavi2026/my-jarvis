"""Test doubles: a fake removable volume provider backed by temporary directories."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from jarvis.storage.volumes import VolumeInfo

GB = 1024**3
HD_GUID = "e6c1df52-3c64-11f1-89fc-a4bb6d60675f"
OTHER_GUID = "11111111-2222-3333-4444-555555555555"


class FakeVolumeProvider:
    def __init__(self) -> None:
        self._volumes: dict[str, VolumeInfo] = {}
        self.fail = False

    def list_volumes(self) -> list[VolumeInfo]:
        if self.fail:
            raise OSError("enumeration failed")
        return list(self._volumes.values())

    def add(self, guid: str, label: str, letter: str, backing: Path, *, fs: str = "exFAT",
            total_gb: float = 298, free_gb: float = 250, read_only: bool = False,
            media: str = "HDD") -> VolumeInfo:
        backing.mkdir(parents=True, exist_ok=True)
        info = VolumeInfo(guid, label, fs, backing, int(total_gb * GB), int(free_gb * GB),
                          read_only, media, letter)
        self._volumes[guid] = info
        return info

    def remove(self, guid: str) -> VolumeInfo:
        return self._volumes.pop(guid)

    def update(self, guid: str, **changes: object) -> None:
        self._volumes[guid] = replace(self._volumes[guid], **changes)  # type: ignore[arg-type]
