"""StorageManager: single source of truth for where JARVIS keeps its files.

Internal tier (SSD): core, config, critical databases, bootstrap logs, fast cache.
External tier (removable HD): models, memory, personal data, documents, logs, backups.

The external volume is matched by GUID. If it is absent or invalid the manager enters
DEGRADED mode: internal categories keep working, external ones raise StorageUnavailable.
Nothing is created, moved or deleted on the external volume except by explicit calls.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path

from .atomic import atomic_write_bytes
from .categories import CATEGORY_SPECS, StorageCategory, Tier
from .config import StorageConfig, load_storage_config, save_storage_config
from .errors import StorageConfigError, StorageError, StorageUnavailable
from .events import StorageEvent, StorageEventKind, StorageListener, dispatch
from .volumes import VolumeInfo, VolumeProvider, normalize_guid

log = logging.getLogger(__name__)

_GB = 1024**3
CONFIG_FILENAME = "config.json"


class StorageMode(str, Enum):
    NORMAL = "NORMAL"
    DEGRADED = "STORAGE_DEGRADED"


class DegradedReason(str, Enum):
    NOT_BOUND = "not_bound"  # no volume GUID recorded yet; the user must confirm a candidate
    VOLUME_MISSING = "volume_missing"
    NO_MOUNT_POINT = "no_mount_point"
    FILESYSTEM_MISMATCH = "filesystem_mismatch"
    ROOT_MISSING = "root_missing"
    NOT_READABLE = "not_readable"
    NOT_WRITABLE = "not_writable"


class SpaceLevel(str, Enum):
    OK = "ok"
    LOW = "low"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class StorageStatus:
    mode: StorageMode
    reason: DegradedReason | None = None
    volume: VolumeInfo | None = None
    root: Path | None = None
    space: SpaceLevel = SpaceLevel.UNKNOWN
    candidates: tuple[VolumeInfo, ...] = ()
    detail: str = ""
    checked_at: float = field(default_factory=time.time)

    @property
    def available(self) -> bool:
        return self.mode is StorageMode.NORMAL


class StorageManager:
    def __init__(
        self,
        internal_root: Path,
        provider: VolumeProvider,
        config: StorageConfig | None = None,
    ) -> None:
        self._internal_root = Path(internal_root)
        self._provider = provider
        self._lock = threading.RLock()
        self._listeners: list[StorageListener] = []
        self._pending_events: list[StorageEvent] = []
        self._ever_normal = False
        self._config_path = self.internal_path(StorageCategory.CONFIG) / CONFIG_FILENAME
        self._config = config if config is not None else self._load_config()
        self._status = StorageStatus(StorageMode.DEGRADED, DegradedReason.VOLUME_MISSING, detail="not initialized")

    # ── configuration ──────────────────────────────────────────────
    def _load_config(self) -> StorageConfig:
        try:
            return load_storage_config(self._config_path)
        except StorageConfigError as exc:
            # Never delete a user file: set the broken one aside and continue with defaults.
            aside = self._config_path.with_name(f"{self._config_path.name}.corrupt-{int(time.time())}")
            try:
                os.replace(self._config_path, aside)
            except OSError:
                pass
            log.error("storage configuration invalid, using defaults (old file kept as %s): %s", aside.name, exc)
            self._pending_events.append(
                StorageEvent(StorageEventKind.RECOVERY, f"configuration reset; old file kept as {aside.name}")
            )
            return StorageConfig()

    @property
    def config(self) -> StorageConfig:
        return self._config

    def add_listener(self, listener: StorageListener) -> None:
        self._listeners.append(listener)

    # ── paths ──────────────────────────────────────────────────────
    def internal_path(self, category: StorageCategory) -> Path:
        spec = CATEGORY_SPECS[category]
        return self._internal_root if spec.subdir == "." else self._internal_root / spec.subdir

    @property
    def status(self) -> StorageStatus:
        return self._status

    @property
    def storage_root(self) -> Path | None:
        """JARVIS_STORAGE_ROOT: runtime data root on the external volume, or None if unavailable."""
        return self._status.root if self._status.available else None

    def get_path(self, category: StorageCategory, *, create: bool = False) -> Path:
        if self._config.tier_of(category) is Tier.INTERNAL:
            path = self.internal_path(category)
        else:
            status = self._status
            if not status.available or status.root is None:
                raise StorageUnavailable(category, status.reason)
            path = status.root / CATEGORY_SPECS[category].subdir
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def is_available(self, category: StorageCategory) -> bool:
        return self._config.tier_of(category) is Tier.INTERNAL or self._status.available

    # ── lifecycle ──────────────────────────────────────────────────
    def initialize(self) -> StorageStatus:
        with self._lock:
            pending, self._pending_events = self._pending_events, []
            for event in pending:
                self._emit(event)
            self.internal_path(StorageCategory.CONFIG).mkdir(parents=True, exist_ok=True)
            return self._apply(self._evaluate(), first=True)

    def refresh(self, *, full: bool = False) -> StorageStatus:
        """Re-evaluate storage. Cheap by default: no disk probe while NORMAL and unchanged."""
        with self._lock:
            current = self._status
            if not full and current.available and current.volume is not None:
                match = self._find_volume(self._provider.list_volumes())
                if (
                    match is not None
                    and match.guid == current.volume.guid
                    and match.mount_path == current.volume.mount_path
                    and not match.read_only
                ):
                    return self._apply(
                        replace(current, volume=match, space=self._space_level(match), checked_at=time.time())
                    )
            return self._apply(self._evaluate())

    def bind(self, volume_guid: str, *, create_root: bool = True) -> StorageStatus:
        """User-confirmed: adopt this volume as the external storage and persist its GUID."""
        with self._lock:
            guid = normalize_guid(volume_guid)
            volume = next((v for v in self._provider.list_volumes() if v.guid == guid), None)
            if volume is None:
                raise StorageError("volume not found; it must be connected to be bound")
            if volume.mount_path is None:
                raise StorageError("volume has no drive letter or mount point")
            new_config = self._config.with_guid(guid)
            if create_root:
                (volume.mount_path / new_config.external.root_dir).mkdir(parents=True, exist_ok=True)
            save_storage_config(self._config_path, new_config)
            self._config = new_config
            return self._apply(self._evaluate())

    def report_io_error(self, exc: BaseException) -> StorageStatus:
        """Callers report failed external I/O; the manager re-validates (the volume may be gone)."""
        with self._lock:
            self._emit(StorageEvent(StorageEventKind.WRITE_ERROR, type(exc).__name__))
            return self._apply(self._evaluate())

    # ── evaluation ─────────────────────────────────────────────────
    def _find_volume(self, volumes: list[VolumeInfo]) -> VolumeInfo | None:
        guid = self._config.external.volume_guid
        return next((v for v in volumes if guid and v.guid == guid), None)

    def _space_level(self, volume: VolumeInfo) -> SpaceLevel:
        free_gb = volume.free_bytes / _GB
        if free_gb < self._config.low_space_critical_gb:
            return SpaceLevel.CRITICAL
        if free_gb < self._config.low_space_warn_gb:
            return SpaceLevel.LOW
        return SpaceLevel.OK

    def _evaluate(self) -> StorageStatus:
        ext = self._config.external
        try:
            volumes = self._provider.list_volumes()
        except Exception as exc:  # a provider failure must never crash the app
            log.error("volume enumeration failed: %s", type(exc).__name__)
            return StorageStatus(StorageMode.DEGRADED, DegradedReason.VOLUME_MISSING, detail="volume enumeration failed")

        if ext.volume_guid is None:
            wanted = ext.volume_label.casefold()
            candidates = tuple(
                v for v in volumes
                if v.label.casefold() == wanted and (ext.filesystem is None or v.filesystem == ext.filesystem)
            )
            return StorageStatus(
                StorageMode.DEGRADED, DegradedReason.NOT_BOUND, candidates=candidates,
                detail=f"{len(candidates)} candidate volume(s) labelled {ext.volume_label}",
            )

        volume = self._find_volume(volumes)
        if volume is None:
            occupant = next((v for v in volumes if ext.preferred_drive and v.drive_letter == ext.preferred_drive), None)
            detail = "expected volume not connected"
            if occupant is not None:
                detail += f"; a different volume is mounted at {ext.preferred_drive} and was NOT used"
            return StorageStatus(StorageMode.DEGRADED, DegradedReason.VOLUME_MISSING, detail=detail)

        def degraded(reason: DegradedReason, detail: str = "", root: Path | None = None) -> StorageStatus:
            return StorageStatus(StorageMode.DEGRADED, reason, volume=volume, root=root, detail=detail)

        if volume.mount_path is None:
            return degraded(DegradedReason.NO_MOUNT_POINT, "volume present but has no drive letter")
        if ext.filesystem is not None and volume.filesystem != ext.filesystem:
            return degraded(DegradedReason.FILESYSTEM_MISMATCH, f"found {volume.filesystem}")
        root = volume.mount_path / ext.root_dir
        try:
            if not root.is_dir():
                return degraded(DegradedReason.ROOT_MISSING, "runtime root folder does not exist")
            with os.scandir(root):
                pass
        except OSError:
            return degraded(DegradedReason.NOT_READABLE, root=root)
        if volume.read_only:
            return degraded(DegradedReason.NOT_WRITABLE, "volume is read-only", root=root)
        if not self._probe_write(root):
            return degraded(DegradedReason.NOT_WRITABLE, "write probe failed", root=root)
        return StorageStatus(StorageMode.NORMAL, volume=volume, root=root, space=self._space_level(volume))

    @staticmethod
    def _probe_write(root: Path) -> bool:
        """Tiny non-destructive write test: create, fsync and delete one temporary file."""
        probe = root / f".jarvis-probe-{uuid.uuid4().hex}.tmp"
        try:
            atomic_write_bytes(probe, b"jarvis-probe")
            probe.unlink()
            return True
        except OSError:
            try:
                probe.unlink()
            except OSError:
                pass
            return False

    # ── transitions and events ─────────────────────────────────────
    def _emit(self, event: StorageEvent) -> None:
        log.info("storage event %s %s", event.kind.value, event.detail)
        dispatch(self._listeners, event)

    def _apply(self, new: StorageStatus, *, first: bool = False) -> StorageStatus:
        old = self._status
        self._status = new
        reason = new.reason.value if new.reason else ""
        if first:
            if new.volume is not None:
                self._emit(StorageEvent(StorageEventKind.FOUND, new.volume.label))
            if new.available:
                self._emit(StorageEvent(StorageEventKind.VALIDATED))
            else:
                self._emit(StorageEvent(StorageEventKind.MISSING, reason))
        elif old.available and not new.available:
            self._emit(StorageEvent(StorageEventKind.REMOVED, reason))
        elif not old.available and new.available:
            kind = StorageEventKind.RECONNECTED if self._ever_normal else StorageEventKind.VALIDATED
            self._emit(StorageEvent(kind))
        elif not old.available and not new.available and old.reason != new.reason:
            self._emit(StorageEvent(StorageEventKind.MISSING, reason))
        if new.available:
            self._ever_normal = True
        if new.space is not old.space or first:
            if new.space is SpaceLevel.CRITICAL:
                self._emit(StorageEvent(StorageEventKind.SPACE_CRITICAL))
            elif new.space is SpaceLevel.LOW:
                self._emit(StorageEvent(StorageEventKind.LOW_SPACE))
        return new
