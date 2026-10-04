from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from jarvis.storage import (CATEGORY_SPECS, StorageCategory, StorageConfig, StorageConfigError, Tier,
                            atomic_write_bytes, atomic_write_json, load_storage_config, normalize_guid,
                            save_storage_config)
from jarvis.storage.config import ExternalIdentity, validate_root_dir


def test_atomic_write_creates_and_replaces(tmp_path: Path) -> None:
    target = tmp_path / "sub" / "file.bin"
    atomic_write_bytes(target, b"one")
    atomic_write_bytes(target, b"two")
    assert target.read_bytes() == b"two"
    assert [p.name for p in target.parent.iterdir()] == ["file.bin"]


def test_failed_atomic_write_keeps_original_and_cleans_temp(tmp_path: Path, monkeypatch) -> None:
    target = tmp_path / "data.json"
    atomic_write_json(target, {"v": 1})

    def boom(src, dst):
        raise OSError("disk disappeared")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        atomic_write_json(target, {"v": 2})
    monkeypatch.undo()
    assert json.loads(target.read_text(encoding="utf-8")) == {"v": 1}
    assert [p.name for p in tmp_path.iterdir()] == ["data.json"]


BS = chr(92)

BAD_ROOTS = ["", "  ", "..", "a/../b", "D:/JARVIS", "C:" + BS + "x", "/abs", BS * 2 + "srv" + BS + "share", "a:b", "x*y", ".", "a" + BS + ".." + BS + "b", ".." + BS + "x"]


@pytest.mark.parametrize("bad", BAD_ROOTS)
def test_invalid_root_dir_rejected(bad: str) -> None:
    with pytest.raises(StorageConfigError):
        validate_root_dir(bad)


def test_valid_root_dir_normalised() -> None:
    assert validate_root_dir("JARVIS") == "JARVIS"
    assert validate_root_dir("Apps" + BS + "JARVIS/") == "Apps/JARVIS"


def test_guid_normalisation() -> None:
    raw = BS * 2 + "?" + BS + "Volume{E6C1DF52-3C64-11F1-89FC-A4BB6D60675F}" + BS
    assert normalize_guid(raw) == "e6c1df52-3c64-11f1-89fc-a4bb6d60675f"
    with pytest.raises(ValueError):
        normalize_guid("not-a-guid")


def test_identity_validation() -> None:
    with pytest.raises(StorageConfigError):
        ExternalIdentity(preferred_drive="DD")
    with pytest.raises(StorageConfigError):
        ExternalIdentity(volume_guid="nope")
    assert ExternalIdentity(preferred_drive="d:").preferred_drive == "D:"


def test_critical_categories_cannot_move_to_external() -> None:
    for category, spec in CATEGORY_SPECS.items():
        if spec.internal_only:
            with pytest.raises(StorageConfigError):
                StorageConfig(tiers={category: Tier.EXTERNAL})
    # non critical categories can be re-mapped
    cfg = StorageConfig(tiers={StorageCategory.CACHE: Tier.EXTERNAL})
    assert cfg.tier_of(StorageCategory.CACHE) is Tier.EXTERNAL


def test_threshold_validation() -> None:
    with pytest.raises(StorageConfigError):
        StorageConfig(low_space_warn_gb=5, low_space_critical_gb=10)


def test_config_roundtrip_preserves_other_sections(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"appearance": {"orb": "bottom-right"}}), encoding="utf-8")
    cfg = StorageConfig().with_guid("E6C1DF52-3C64-11F1-89FC-A4BB6D60675F")
    save_storage_config(path, cfg)
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["appearance"] == {"orb": "bottom-right"}
    loaded = load_storage_config(path)
    assert loaded.external.volume_guid == "e6c1df52-3c64-11f1-89fc-a4bb6d60675f"


def test_missing_config_gives_defaults(tmp_path: Path) -> None:
    assert load_storage_config(tmp_path / "nope.json").external.volume_label == "HD JD"


@pytest.mark.parametrize("content", ["{not json", "[]", json.dumps({"storage": {"external": {"root_dir": ".."}}}),
                                     json.dumps({"storage": {"categories": {"bogus": "internal"}}})])
def test_invalid_config_raises(tmp_path: Path, content: str) -> None:
    path = tmp_path / "config.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(StorageConfigError):
        load_storage_config(path)


def test_every_category_has_a_spec() -> None:
    assert set(CATEGORY_SPECS) == set(StorageCategory)
