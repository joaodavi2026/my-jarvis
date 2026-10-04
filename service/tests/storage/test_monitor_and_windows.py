from __future__ import annotations

import asyncio
import sys

import pytest

from jarvis.storage import StorageMonitor, StorageMode
from jarvis.storage.windows_volumes import WindowsVolumeProvider

from .fakes import HD_GUID


async def _wait_for(predicate, timeout: float = 2.0) -> None:
    deadline = asyncio.get_running_loop().time() + timeout
    while not predicate():
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError("condition not reached in time")
        await asyncio.sleep(0.01)


async def test_monitor_detects_removal_and_return(make_manager, bound_config, connected, provider):
    manager = make_manager(bound_config)
    manager.initialize()
    monitor = StorageMonitor(manager, interval=0.01)
    monitor.start()
    try:
        provider.remove(HD_GUID)
        await _wait_for(lambda: manager.status.mode is StorageMode.DEGRADED)
        provider.add(HD_GUID, "HD JD", "Q:", connected.mount_path)
        await _wait_for(lambda: manager.status.mode is StorageMode.NORMAL)
    finally:
        await monitor.stop()


async def test_monitor_stop_is_idempotent(make_manager, bound_config, connected):
    monitor = StorageMonitor(make_manager(bound_config), interval=0.01)
    monitor.start()
    await monitor.stop()
    await monitor.stop()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows only")
def test_real_windows_provider_is_read_only_and_well_formed():
    volumes = WindowsVolumeProvider().list_volumes()
    assert volumes, "expected at least the system drive"
    for volume in volumes:
        assert len(volume.guid) == 36 and volume.guid == volume.guid.lower()
        assert volume.letter and len(volume.letter) == 2 and volume.letter.endswith(":")
        assert volume.total_bytes >= volume.free_bytes >= 0
        assert volume.media_type in {"HDD", "SSD", "UNKNOWN"}
