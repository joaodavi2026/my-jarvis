"""Envelope for the Rust <-> Python protocol (contracts/protocol.md, version 1)."""

from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from typing import Any, Literal

PROTOCOL_VERSION = 1
MAX_MESSAGE_BYTES = 1 << 20  # 1 MiB

Kind = Literal["req", "res", "evt"]
_KINDS = ("req", "res", "evt")
_TYPE_RE = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$")

# Close codes (application range)
CLOSE_UNAUTHORIZED = 4401
CLOSE_BUSY = 4409


class ProtocolError(ValueError):
    """The peer sent something that is not a valid v1 envelope."""


@dataclass(frozen=True)
class Envelope:
    kind: Kind
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    id: str | None = None
    ts: float = field(default_factory=time.time)

    def to_json(self) -> str:
        body: dict[str, Any] = {"v": PROTOCOL_VERSION, "kind": self.kind, "type": self.type,
                                "ts": self.ts, "payload": self.payload}
        if self.id is not None:
            body["id"] = self.id
        return json.dumps(body, separators=(",", ":"), ensure_ascii=False)


def parse(raw: str | bytes) -> Envelope:
    if isinstance(raw, bytes):
        raise ProtocolError("binary frames are not supported")
    if len(raw.encode("utf-8")) > MAX_MESSAGE_BYTES:
        raise ProtocolError("message too large")
    try:
        data = json.loads(raw)
    except ValueError as exc:
        raise ProtocolError("invalid JSON") from exc
    if not isinstance(data, dict):
        raise ProtocolError("envelope must be an object")
    if data.get("v") != PROTOCOL_VERSION:
        raise ProtocolError("unsupported protocol version")
    kind, type_ = data.get("kind"), data.get("type")
    if kind not in _KINDS:
        raise ProtocolError("invalid kind")
    if not isinstance(type_, str) or not _TYPE_RE.match(type_):
        raise ProtocolError("invalid type")
    msg_id = data.get("id")
    if msg_id is not None and not isinstance(msg_id, str):
        raise ProtocolError("id must be a string")
    if kind in ("req", "res") and not msg_id:
        raise ProtocolError("req/res require an id")
    payload = data.get("payload", {})
    if not isinstance(payload, dict):
        raise ProtocolError("payload must be an object")
    return Envelope(kind, type_, payload, msg_id)  # type: ignore[arg-type]


def ok_response(request: Envelope, payload: dict[str, Any] | None = None) -> Envelope:
    return Envelope("res", request.type, {"ok": True, **(payload or {})}, request.id)


def error_response(request: Envelope, error: str, message: str = "") -> Envelope:
    return Envelope("res", request.type, {"ok": False, "error": error, "message": message}, request.id)
