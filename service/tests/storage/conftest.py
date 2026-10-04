from __future__ import annotations

from pathlib import Path

import pytest

from jarvis.storage import StorageConfig, StorageEvent, StorageManager
from jarvis.storage.config import ExternalIdentity

from .fakes import HD_GUID, FakeVolumeProvider


class Recorder:
    def __init__(self) -> None:
        self.events: list[StorageEvent] = []

    def __call__(self, event: StorageEvent) -> None:
        self.events.append(event)

    @property
    def kinds(self) -> list[str]:
        return [e.kind.value for e in self.events]


@pytest.fixture
def internal(tmp_path: Path) -> Path:
    return tmp_path / "ssd" / "JARVIS"


@pytest.fixture
def disk(tmp_path: Path) -> Path:
    return tmp_path / "hd_backing"


@pytest.fixture
def provider() -> FakeVolumeProvider:
    return FakeVolumeProvider()


@pytest.fixture
def recorder() -> Recorder:
    return Recorder()


@pytest.fixture
def bound_config() -> StorageConfig:
    return StorageConfig(ExternalIdentity(volume_label="HD JD", volume_guid=HD_GUID,
                                          preferred_drive="Q:", root_dir="JARVIS"))


@pytest.fixture
def make_manager(internal: Path, provider: FakeVolumeProvider, recorder: Recorder):
    def _make(config: StorageConfig | None = None) -> StorageManager:
        manager = StorageManager(internal, provider, config)
        manager.add_listener(recorder)
        return manager
    return _make


@pytest.fixture
def connected(provider: FakeVolumeProvider, disk: Path):
    """The HD is plugged in as Q: and its runtime root already exists."""
    info = provider.add(HD_GUID, "HD JD", "Q:", disk)
    (disk / "JARVIS").mkdir(parents=True, exist_ok=True)
    return info
