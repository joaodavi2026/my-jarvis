"""Lightweight health snapshot. No polling: it is computed on request from current state."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

# Capabilities that exist in the roadmap but are not implemented yet. Reported honestly.
PLANNED_CAPABILITIES = ("audio", "wake_word", "stt", "tts", "local_ai", "router", "tools", "memory", "google")


class HealthService:
    def __init__(self, state: Callable[[], str], storage: Callable[[], dict[str, Any]],
                 ipc_connected: Callable[[], bool]) -> None:
        self._state = state
        self._storage = storage
        self._ipc_connected = ipc_connected
        self._started = time.monotonic()

    def snapshot(self) -> dict[str, Any]:
        capabilities: dict[str, Any] = {name: {"status": "UNAVAILABLE", "reason": "not_implemented"}
                                        for name in PLANNED_CAPABILITIES}
        storage = self._storage()
        capabilities["storage"] = {"status": "AVAILABLE" if storage["mode"] == "NORMAL" else "DEGRADED", **storage}
        capabilities["ipc"] = {"status": "AVAILABLE", "client_connected": self._ipc_connected()}
        return {
            "service": "ok",
            "uptime_s": round(time.monotonic() - self._started, 1),
            "state": self._state(),
            "capabilities": capabilities,
        }
