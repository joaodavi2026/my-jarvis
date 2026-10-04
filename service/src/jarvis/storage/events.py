from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Callable

log = logging.getLogger(__name__)


class StorageEventKind(str, Enum):
    FOUND = "STORAGE_FOUND"
    VALIDATED = "STORAGE_VALIDATED"
    MISSING = "STORAGE_MISSING"
    REMOVED = "STORAGE_REMOVED"
    RECONNECTED = "STORAGE_RECONNECTED"
    LOW_SPACE = "STORAGE_LOW_SPACE"
    SPACE_CRITICAL = "STORAGE_SPACE_CRITICAL"
    WRITE_ERROR = "STORAGE_WRITE_ERROR"
    RECOVERY = "STORAGE_RECOVERY"


@dataclass(frozen=True)
class StorageEvent:
    kind: StorageEventKind
    detail: str = ""


StorageListener = Callable[[StorageEvent], None]


def dispatch(listeners: list[StorageListener], event: StorageEvent) -> None:
    """A failing listener never breaks storage handling or other listeners."""
    for listener in list(listeners):
        try:
            listener(event)
        except Exception:
            log.exception("storage listener failed", extra={"event": event.kind.value})
