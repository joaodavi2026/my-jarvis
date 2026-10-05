"""Single-instance guard: a second jarvis-show must not start a second listener or open more browser tabs."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from types import TracebackType


LOCK_OFFSET = 4096


class AlreadyRunning(RuntimeError):
    pass


class InstanceLock:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or Path(tempfile.gettempdir()) / "jarvis-show.lock"
        self._file = None

    def __enter__(self) -> "InstanceLock":
        import msvcrt  # Windows only, like the rest of this project

        self._file = open(self.path, "a+")
        try:
            self._file.seek(LOCK_OFFSET)  # lock a byte far from the pid text: a locked region cannot be written, even by us
            msvcrt.locking(self._file.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            self._file.close()
            self._file = None
            raise AlreadyRunning("jarvis-show is already running") from None
        self._file.seek(0)
        self._file.truncate(0)
        self._file.write(str(os.getpid()))
        self._file.flush()
        return self

    def __exit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: TracebackType | None) -> None:
        import msvcrt

        if self._file is not None:
            try:
                self._file.seek(LOCK_OFFSET)
                msvcrt.locking(self._file.fileno(), msvcrt.LK_UNLCK, 1)
            finally:
                self._file.close()
