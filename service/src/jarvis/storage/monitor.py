from __future__ import annotations

import asyncio
import contextlib
import logging

from .manager import StorageManager

log = logging.getLogger(__name__)


class StorageMonitor:
    """Detects HD removal/return while JARVIS runs.

    Polls the cheap volume list; the manager only touches the disk when something changed.
    """

    def __init__(self, manager: StorageManager, interval: float = 5.0) -> None:
        self._manager = manager
        self._interval = interval
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.get_running_loop().create_task(self._run(), name="storage-monitor")

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None

    async def _run(self) -> None:
        while True:
            try:
                await asyncio.to_thread(self._manager.refresh)
            except Exception:
                log.exception("storage refresh failed")
            await asyncio.sleep(self._interval)
