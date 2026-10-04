"""In-process asynchronous event bus. Handlers are isolated: one failing never affects others."""

from __future__ import annotations

import asyncio
import inspect
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Event:
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: str | None = None
    ts: float = field(default_factory=time.time)


Handler = Callable[[Event], Awaitable[None] | None]


def _matches(pattern: str, event_type: str) -> bool:
    if pattern == "*":
        return True
    if pattern.endswith(".*"):
        return event_type.startswith(pattern[:-1])
    return pattern == event_type


class EventBus:
    def __init__(self) -> None:
        self._subscribers: list[tuple[str, Handler]] = []
        self._tasks: set[asyncio.Task[None]] = set()

    def subscribe(self, pattern: str, handler: Handler) -> Callable[[], None]:
        """Pattern: exact type, prefix such as state.* , or *. Returns an unsubscribe function."""
        entry = (pattern, handler)
        self._subscribers.append(entry)

        def unsubscribe() -> None:
            if entry in self._subscribers:
                self._subscribers.remove(entry)

        return unsubscribe

    def publish(self, type: str, payload: dict[str, Any] | None = None, *, correlation_id: str | None = None) -> Event:
        event = Event(type, dict(payload or {}), correlation_id)
        for pattern, handler in list(self._subscribers):
            if _matches(pattern, type):
                self._dispatch(handler, event)
        return event

    def _dispatch(self, handler: Handler, event: Event) -> None:
        try:
            result = handler(event)
        except Exception:
            log.exception("event handler failed", extra={"event_type": event.type})
            return
        if inspect.isawaitable(result):
            task = asyncio.get_running_loop().create_task(self._guard(result, event))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

    @staticmethod
    async def _guard(awaitable: Awaitable[None], event: Event) -> None:
        try:
            await awaitable
        except Exception:
            log.exception("async event handler failed", extra={"event_type": event.type})

    async def drain(self) -> None:
        """Waits for in-flight async handlers (used by tests and shutdown)."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)
