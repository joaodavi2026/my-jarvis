from __future__ import annotations


class StorageError(Exception):
    """Base class for storage failures."""


class StorageConfigError(StorageError):
    """The storage configuration is missing required data or is invalid."""


class StorageUnavailable(StorageError):
    """A category that lives on the external volume was requested while it is unavailable."""

    def __init__(self, category: object, reason: object) -> None:
        super().__init__(f"STORAGE_UNAVAILABLE: {getattr(category, 'value', category)} ({getattr(reason, 'value', reason)})")
        self.category = category
        self.reason = reason
