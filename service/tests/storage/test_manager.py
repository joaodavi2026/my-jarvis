from __future__ import annotations

import json

import pytest

from jarvis.storage import (DegradedReason, SpaceLevel, StorageCategory, StorageConfig, StorageError,
                            StorageManager, StorageMode, StorageUnavailable)
from jarvis.storage import manager as manager_module
from jarvis.storage.config import ExternalIdentity

from .fakes import HD_GUID, OTHER_GUID

EXTERNAL = [StorageCategory.LLM_MODELS, StorageCategory.MEMORY, StorageCategory.PERSONAL_DATA,
            StorageCategory.LOGS, StorageCategory.BACKUPS, StorageCategory.TEMP]
INTERNAL = [StorageCategory.CORE, StorageCategory.CONFIG, StorageCategory.DATABASE,
            StorageCategory.BOOTSTRAP_LOGS, StorageCategory.CACHE]


def test_drive_present_is_normal(make_manager, bound_config, connected, disk, recorder):
    manager = make_manager(bound_config)
    status = manager.initialize()
    assert status.mode is StorageMode.NORMAL and status.available
    assert manager.storage_root == disk / "JARVIS"
    assert manager.get_path(StorageCategory.LLM_MODELS) == disk / "JARVIS" / "Models" / "LLM"
    assert manager.get_path(StorageCategory.MEMORY) == disk / "JARVIS" / "Memory"
    assert recorder.kinds == ["STORAGE_FOUND", "STORAGE_VALIDATED"]


def test_probe_leaves_no_files_behind(make_manager, bound_config, connected, disk):
    make_manager(bound_config).initialize()
    assert list((disk / "JARVIS").iterdir()) == []


def test_drive_absent_is_degraded_without_crash(make_manager, bound_config, provider, disk, recorder):
    manager = make_manager(bound_config)
    status = manager.initialize()
    assert status.mode is StorageMode.DEGRADED and status.reason is DegradedReason.VOLUME_MISSING
    assert manager.storage_root is None
    for category in INTERNAL:
        assert manager.is_available(category)
        manager.get_path(category)
    for category in EXTERNAL:
        assert not manager.is_available(category)
        with pytest.raises(StorageUnavailable):
            manager.get_path(category)
    assert not disk.exists()
    assert recorder.kinds == ["STORAGE_MISSING"]


def test_internal_paths_stay_under_internal_root(make_manager, bound_config, internal):
    manager = make_manager(bound_config)
    for category in INTERNAL:
        path = manager.get_path(category)
        assert path == internal or internal in path.parents


def test_unbound_first_run_offers_candidates_and_does_not_autobind(make_manager, provider, disk, internal):
    provider.add(HD_GUID, "HD JD", "Q:", disk)
    provider.add(OTHER_GUID, "OUTRO", "R:", disk.parent / "other")
    manager = make_manager()
    status = manager.initialize()
    assert status.reason is DegradedReason.NOT_BOUND
    assert [v.guid for v in status.candidates] == [HD_GUID]
    assert not (disk / "JARVIS").exists()
    assert not (internal / "config" / "config.json").exists()


def test_bind_creates_root_persists_guid_and_survives_restart(make_manager, provider, disk, internal):
    provider.add(HD_GUID, "HD JD", "Q:", disk)
    manager = make_manager()
    manager.initialize()
    status = manager.bind(HD_GUID)
    assert status.available and (disk / "JARVIS").is_dir()
    saved = json.loads((internal / "config" / "config.json").read_text(encoding="utf-8"))
    assert saved["storage"]["external"]["volume_guid"] == HD_GUID
    again = StorageManager(internal, provider)
    assert again.initialize().available


def test_bind_requires_connected_volume(make_manager):
    manager = make_manager()
    manager.initialize()
    with pytest.raises(StorageError):
        manager.bind(HD_GUID)


def test_drive_letter_changed_is_still_recognised(make_manager, bound_config, connected, provider):
    manager = make_manager(bound_config)
    manager.initialize()
    provider.update(HD_GUID, letter="E:")
    status = manager.refresh()
    assert status.available and status.volume.drive_letter == "E:"


def test_wrong_drive_at_preferred_letter_is_refused(make_manager, bound_config, provider, disk):
    impostor = disk.parent / "impostor"
    provider.add(OTHER_GUID, "HD JD", "Q:", impostor)
    (impostor / "JARVIS").mkdir()
    manager = make_manager(bound_config)
    status = manager.initialize()
    assert status.reason is DegradedReason.VOLUME_MISSING
    assert "NOT used" in status.detail
    with pytest.raises(StorageUnavailable):
        manager.get_path(StorageCategory.MEMORY)
    assert list((impostor / "JARVIS").iterdir()) == []


def test_read_only_volume_is_degraded(make_manager, bound_config, provider, disk):
    provider.add(HD_GUID, "HD JD", "Q:", disk, read_only=True)
    (disk / "JARVIS").mkdir()
    assert make_manager(bound_config).initialize().reason is DegradedReason.NOT_WRITABLE


def test_failed_write_probe_is_degraded(make_manager, bound_config, connected, monkeypatch):
    def boom(path, data):
        raise OSError("write failed")

    monkeypatch.setattr(manager_module, "atomic_write_bytes", boom)
    assert make_manager(bound_config).initialize().reason is DegradedReason.NOT_WRITABLE


def test_missing_root_is_not_silently_recreated(make_manager, bound_config, provider, disk):
    provider.add(HD_GUID, "HD JD", "Q:", disk)
    status = make_manager(bound_config).initialize()
    assert status.reason is DegradedReason.ROOT_MISSING
    assert not (disk / "JARVIS").exists()


def test_filesystem_mismatch(make_manager, connected):
    cfg = StorageConfig(ExternalIdentity(volume_guid=HD_GUID, preferred_drive="Q:", filesystem="NTFS"))
    assert make_manager(cfg).initialize().reason is DegradedReason.FILESYSTEM_MISMATCH


@pytest.mark.parametrize("free_gb,level,event", [
    (250, SpaceLevel.OK, None),
    (15, SpaceLevel.LOW, "STORAGE_LOW_SPACE"),
    (2, SpaceLevel.CRITICAL, "STORAGE_SPACE_CRITICAL"),
])
def test_low_space_levels_do_not_degrade(make_manager, bound_config, provider, disk, recorder, free_gb, level, event):
    provider.add(HD_GUID, "HD JD", "Q:", disk, free_gb=free_gb)
    (disk / "JARVIS").mkdir()
    status = make_manager(bound_config).initialize()
    assert status.available and status.space is level
    if event:
        assert event in recorder.kinds
    else:
        assert "STORAGE_LOW_SPACE" not in recorder.kinds


def test_space_worsening_emits_event_on_refresh(make_manager, bound_config, connected, provider, recorder):
    manager = make_manager(bound_config)
    manager.initialize()
    provider.update(HD_GUID, free_bytes=int(3 * 1024**3))
    manager.refresh()
    assert recorder.kinds[-1] == "STORAGE_SPACE_CRITICAL"


def test_hot_remove_and_reconnect(make_manager, bound_config, connected, provider, recorder):
    manager = make_manager(bound_config)
    manager.initialize()
    provider.remove(HD_GUID)
    assert manager.refresh().reason is DegradedReason.VOLUME_MISSING
    with pytest.raises(StorageUnavailable):
        manager.get_path(StorageCategory.MEMORY)
    manager.get_path(StorageCategory.DATABASE)
    provider.add(HD_GUID, "HD JD", "Q:", connected.mount_path)
    assert manager.refresh().available
    manager.get_path(StorageCategory.MEMORY)
    assert recorder.kinds == ["STORAGE_FOUND", "STORAGE_VALIDATED", "STORAGE_REMOVED", "STORAGE_RECONNECTED"]


def test_disconnect_during_write_is_detected(make_manager, bound_config, connected, provider, recorder):
    manager = make_manager(bound_config)
    manager.initialize()
    manager.get_path(StorageCategory.MEMORY, create=True)
    provider.remove(HD_GUID)
    status = manager.report_io_error(OSError("write failed"))
    assert status.mode is StorageMode.DEGRADED
    assert "STORAGE_WRITE_ERROR" in recorder.kinds and "STORAGE_REMOVED" in recorder.kinds


def test_refresh_does_not_touch_disk_when_unchanged(make_manager, bound_config, connected, monkeypatch):
    manager = make_manager(bound_config)
    manager.initialize()
    probes = []

    def fake_probe(root):
        probes.append(root)
        return True

    monkeypatch.setattr(StorageManager, "_probe_write", staticmethod(fake_probe))
    for _ in range(5):
        assert manager.refresh().available
    assert probes == []
    manager.refresh(full=True)
    assert len(probes) == 1


def test_provider_failure_does_not_crash(make_manager, bound_config, connected, provider):
    manager = make_manager(bound_config)
    manager.initialize()
    provider.fail = True
    assert manager.refresh(full=True).mode is StorageMode.DEGRADED
    provider.fail = False
    assert manager.refresh().available


def test_listener_exception_is_isolated(make_manager, bound_config, connected, recorder):
    def bad_listener(event):
        raise RuntimeError("listener bug")

    manager = make_manager(bound_config)
    manager.add_listener(bad_listener)
    manager.initialize()
    assert recorder.kinds[0] == "STORAGE_FOUND"


def test_corrupted_config_is_set_aside_not_deleted(internal, provider, recorder):
    config_dir = internal / "config"
    config_dir.mkdir(parents=True)
    (config_dir / "config.json").write_text("{broken", encoding="utf-8")
    manager = StorageManager(internal, provider)
    manager.add_listener(recorder)
    manager.initialize()
    assert any(p.name.startswith("config.json.corrupt-") for p in config_dir.iterdir())
    assert "STORAGE_RECOVERY" in recorder.kinds
    assert manager.config.external.volume_guid is None


def test_invalid_path_in_config_is_treated_as_corrupted(internal, provider):
    config_dir = internal / "config"
    config_dir.mkdir(parents=True)
    bad = {"storage": {"external": {"root_dir": ".."}}}
    (config_dir / "config.json").write_text(json.dumps(bad), encoding="utf-8")
    manager = StorageManager(internal, provider)
    assert manager.config.external.root_dir == "JARVIS"
