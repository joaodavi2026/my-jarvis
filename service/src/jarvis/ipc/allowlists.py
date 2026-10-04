"""Which events may cross the IPC boundary, in each direction (contracts/event-catalog.md)."""

from __future__ import annotations

# Service -> UI. Anything not listed stays inside the service.
OUTBOUND_TYPES = frozenset({
    "state.changed", "service.ready", "service.stopping", "health.changed", "capability.changed",
    "listening.started", "listening.stopped", "audio.level", "stt.partial", "stt.transcription_ready",
    "tts.started", "tts.finished", "tts.interrupted", "ai.thinking", "plan.created", "plan.step_updated",
    "confirmation.requested", "tool.started", "tool.completed", "tool.failed", "privacy.changed",
    "storage.status_changed", "error.occurred", "feedback.pulse",
})

# High-frequency events: dropped first when a client is slow.
DROPPABLE_TYPES = frozenset({"audio.level", "stt.partial"})

# UI -> service. The client may only publish these (or shell.*); it can never forge internal events.
INBOUND_TYPES = frozenset({
    "activation.orb_clicked", "activation.hotkey_pressed", "activation.cancelled", "confirmation.answered",
})
INBOUND_PREFIXES = ("shell.",)


def inbound_allowed(event_type: str) -> bool:
    return event_type in INBOUND_TYPES or event_type.startswith(INBOUND_PREFIXES)
