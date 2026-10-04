"""Storage section of the bootstrap configuration (lives on the internal SSD)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Any

from .atomic import atomic_write_json
from .categories import CATEGORY_SPECS, StorageCategory, Tier
from .errors import StorageConfigError
from .volumes import normalize_guid

_DRIVE_RE = re.compile(r"^[A-Za-z]:$")
_FORBIDDEN_CHARS = set('<>:"|?*')


def validate_root_dir(root_dir: str) -> str:
    """The runtime root must be a safe relative path (no drive, no traversal)."""
    if not isinstance(root_dir, str) or not root_dir.strip():
        raise StorageConfigError("root_dir must be a non-empty string")
    pure = PureWindowsPath(root_dir)
    if pure.is_absolute() or pure.drive or pure.root:
        raise StorageConfigError("root_dir must be relative to the volume")
    parts = [p for p in re.split("[/" + chr(92) * 2 + "]+", root_dir) if p]
    if not parts or any(p in (".", "..") for p in parts):
        raise StorageConfigError("root_dir must not contain dot segments")
    if any(_FORBIDDEN_CHARS & set(p) for p in parts):
        raise StorageConfigError("root_dir contains characters not allowed in Windows paths")
    return "/".join(parts)


@dataclass(frozen=True)
class ExternalIdentity:
    volume_label: str = "HD JD"
    volume_guid: str | None = None
    preferred_drive: str | None = "D:"
    filesystem: str | None = None
    root_dir: str = "JARVIS"

    def __post_init__(self) -> None:
        object.__setattr__(self, "root_dir", validate_root_dir(self.root_dir))
        if not self.volume_label.strip():
            raise StorageConfigError("volume_label must not be empty")
        if self.volume_guid is not None:
            try:
                object.__setattr__(self, "volume_guid", normalize_guid(self.volume_guid))
            except ValueError as exc:
                raise StorageConfigError("volume_guid is not a valid GUID") from exc
        if self.preferred_drive is not None:
            if not _DRIVE_RE.match(self.preferred_drive):
                raise StorageConfigError("preferred_drive must look like D:")
            object.__setattr__(self, "preferred_drive", self.preferred_drive.upper())


@dataclass(frozen=True)
class StorageConfig:
    external: ExternalIdentity = field(default_factory=ExternalIdentity)
    tiers: dict[StorageCategory, Tier] = field(default_factory=dict)
    low_space_warn_gb: float = 20.0
    low_space_critical_gb: float = 5.0
    fast_cache_limit_gb: float = 2.0

    def __post_init__(self) -> None:
        if not 0 < self.low_space_critical_gb <= self.low_space_warn_gb:
            raise StorageConfigError("require 0 < low_space_critical_gb <= low_space_warn_gb")
        if self.fast_cache_limit_gb <= 0:
            raise StorageConfigError("fast_cache_limit_gb must be positive")
        for category, tier in self.tiers.items():
            if CATEGORY_SPECS[category].internal_only and tier is not Tier.INTERNAL:
                raise StorageConfigError(f"{category.value} must stay on the internal drive")

    def tier_of(self, category: StorageCategory) -> Tier:
        return self.tiers.get(category, CATEGORY_SPECS[category].default_tier)

    def with_guid(self, guid: str) -> "StorageConfig":
        ext = self.external
        return StorageConfig(
            ExternalIdentity(ext.volume_label, guid, ext.preferred_drive, ext.filesystem, ext.root_dir),
            self.tiers, self.low_space_warn_gb, self.low_space_critical_gb, self.fast_cache_limit_gb,
        )

    def to_dict(self) -> dict[str, Any]:
        ext = self.external
        return {
            "external": {
                "volume_label": ext.volume_label,
                "volume_guid": ext.volume_guid,
                "preferred_drive": ext.preferred_drive,
                "filesystem": ext.filesystem,
                "root_dir": ext.root_dir,
            },
            "categories": {c.value: t.value for c, t in self.tiers.items()},
            "low_space_warn_gb": self.low_space_warn_gb,
            "low_space_critical_gb": self.low_space_critical_gb,
            "fast_cache_limit_gb": self.fast_cache_limit_gb,
        }

    @classmethod
    def from_dict(cls, data: Any) -> "StorageConfig":
        if not isinstance(data, dict):
            raise StorageConfigError("storage section must be an object")
        ext = data.get("external", {})
        if not isinstance(ext, dict):
            raise StorageConfigError("storage.external must be an object")
        try:
            identity = ExternalIdentity(
                volume_label=ext.get("volume_label", "HD JD"),
                volume_guid=ext.get("volume_guid"),
                preferred_drive=ext.get("preferred_drive", "D:"),
                filesystem=ext.get("filesystem"),
                root_dir=ext.get("root_dir", "JARVIS"),
            )
            tiers: dict[StorageCategory, Tier] = {}
            for name, tier in (data.get("categories") or {}).items():
                tiers[StorageCategory(name)] = Tier(tier)
            return cls(
                identity, tiers,
                float(data.get("low_space_warn_gb", 20.0)),
                float(data.get("low_space_critical_gb", 5.0)),
                float(data.get("fast_cache_limit_gb", 2.0)),
            )
        except StorageConfigError:
            raise
        except (ValueError, TypeError) as exc:
            raise StorageConfigError(f"invalid storage configuration: {exc}") from exc


def load_storage_config(path: Path) -> StorageConfig:
    """Missing file -> defaults. Unreadable or invalid content -> StorageConfigError."""
    path = Path(path)
    if not path.exists():
        return StorageConfig()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise StorageConfigError(f"cannot read {path.name}: {exc}") from exc
    if not isinstance(raw, dict):
        raise StorageConfigError("configuration root must be an object")
    return StorageConfig.from_dict(raw.get("storage", {}))


def save_storage_config(path: Path, config: StorageConfig) -> None:
    """Writes only the storage section, preserving any other top-level keys."""
    path = Path(path)
    existing: dict[str, Any] = {}
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                existing = loaded
        except (OSError, ValueError):
            pass
    existing["storage"] = config.to_dict()
    atomic_write_json(path, existing)
