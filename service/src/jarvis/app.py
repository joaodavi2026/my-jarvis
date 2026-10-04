"""ServiceApp wires storage, event bus, state machine and IPC. Phase 5 scope: no audio or AI yet."""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Any

from .core.events import Event, EventBus
from .core.state import InteractionMachine
from .health import HealthService
from .ipc.protocol import Envelope
from .ipc.server import IpcServer
from .storage import StorageEvent, StorageManager, StorageMonitor, StorageStatus, VolumeProvider

log = logging.getLogger(__name__)


def storage_summary(status: StorageStatus) -> dict[str, Any]:
    return {
        "mode": "NORMAL" if status.available else "DEGRADED",
        "reason": status.reason.value if status.reason else None,
        "space": status.space.value,
        "detail": status.detail,
    }


class ServiceApp:
    def __init__(self, *, token: str, internal_root: Path, provider: VolumeProvider,
                 contract_path: Path | None = None, monitor_interval: float = 5.0, ipc_port: int = 0,
                 handshake_timeout: float = 2.0) -> None:
        self.bus = EventBus()
        self.storage = StorageManager(internal_root, provider)
        self.machine = InteractionMachine.from_file(contract_path, on_change=self._on_state_change)
        self.ipc = IpcServer(token, self.bus, port=ipc_port, handshake_timeout=handshake_timeout)
        self.health = HealthService(lambda: self.machine.state, lambda: storage_summary(self.storage.status),
                                    lambda: self.ipc.connected)
        self._monitor = StorageMonitor(self.storage, monitor_interval)
        self._loop: asyncio.AbstractEventLoop | None = None
        self.ipc.register("ping", lambda _req: {})
        self.ipc.register("state.get", lambda _req: {"state": self.machine.state})
        self.ipc.register("health.get", lambda _req: self.health.snapshot())
        self.ipc.register("storage.get", lambda _req: storage_summary(self.storage.status))
        if os.environ.get("JARVIS_DEV_TOOLS") == "1":
            # Test hook only: drives the REAL state machine (events still flow bus -> IPC -> UI).
            self.ipc.register("dev.dispatch_trigger", self._dev_dispatch_trigger)
        self.bus.subscribe("activation.orb_clicked", self._on_orb_clicked)
        self.bus.subscribe("activation.cancelled", self._on_cancelled)

    # ── lifecycle ──────────────────────────────────────────────────
    async def start(self) -> int:
        self._loop = asyncio.get_running_loop()
        self.storage.add_listener(self._on_storage_event_threadsafe)
        await asyncio.to_thread(self.storage.initialize)  # may touch the slow external disk
        port = await self.ipc.start()
        self.machine.dispatch("boot_completed")
        self._monitor.start()
        self.bus.publish("service.ready", {"protocol": 1})
        self.bus.publish("storage.status_changed", storage_summary(self.storage.status))
        return port

    async def stop(self) -> None:
        self.bus.publish("service.stopping")
        await self._monitor.stop()
        await self.ipc.stop()
        await self.bus.drain()

    # ── storage events (the listener may run on the monitor thread) ─
    def _on_storage_event_threadsafe(self, event: StorageEvent) -> None:
        loop = self._loop
        if loop is not None and not loop.is_closed():
            loop.call_soon_threadsafe(self._publish_storage_event, event)

    def _publish_storage_event(self, event: StorageEvent) -> None:
        self.bus.publish(f"storage.{event.kind.name.lower()}", {"detail": event.detail})
        self.bus.publish("storage.status_changed", storage_summary(self.storage.status))

    # ── state machine -> events ────────────────────────────────────
    def _on_state_change(self, previous: str, state: str, trigger: str) -> None:
        self.bus.publish("state.changed", {"state": state, "previous": previous, "trigger": trigger})

    # ── activation: audio does not exist yet, so never pretend to listen ──
    def _on_orb_clicked(self, _event: Event) -> None:
        if self.machine.state != "IDLE":
            return
        self.bus.publish("error.occurred", {"code": "audio_unavailable",
                                            "message": "A captura de áudio ainda não foi implementada."})
        self.bus.publish("feedback.pulse", {"kind": "ERROR"})

    def _on_cancelled(self, _event: Event) -> None:
        if self.machine.dispatch("cancel_requested"):
            self.machine.dispatch("cancel_completed")

    def _dev_dispatch_trigger(self, request: Envelope) -> dict[str, Any]:
        trigger = request.payload.get("trigger")
        if not isinstance(trigger, str):
            raise ValueError("trigger must be a string")
        accepted = self.machine.dispatch(trigger)
        return {"accepted": accepted, "state": self.machine.state}
