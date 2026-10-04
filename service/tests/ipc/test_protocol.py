from __future__ import annotations

import json

import pytest

from jarvis.ipc.protocol import Envelope, ProtocolError, error_response, ok_response, parse


def raw(**over):
    base = {"v": 1, "kind": "req", "id": "1", "type": "ping", "payload": {}}
    base.update(over)
    return json.dumps({k: v for k, v in base.items() if v is not None})


def test_valid_envelopes_roundtrip():
    request = parse(raw())
    assert (request.kind, request.type, request.id) == ("req", "ping", "1")
    event = parse(raw(kind="evt", id=None, type="state.changed", payload={"state": "IDLE"}))
    assert event.payload == {"state": "IDLE"}
    assert parse(Envelope("evt", "audio.level", {"level": 0.5}).to_json()).payload["level"] == 0.5


@pytest.mark.parametrize("bad", [
    "not json", "[]", "42", raw(v=2), raw(v=None), raw(kind="cmd"), raw(type="Bad Type"), raw(type=""),
    raw(type="a..b"), raw(type="UPPER"), raw(id=None), raw(id=7), raw(payload=[1]), raw(payload="x"),
])
def test_invalid_envelopes_are_rejected(bad):
    with pytest.raises(ProtocolError):
        parse(bad)


def test_binary_and_oversized_frames_are_rejected():
    with pytest.raises(ProtocolError):
        parse(b"{}")
    with pytest.raises(ProtocolError):
        parse(raw(payload={"x": "a" * (1 << 20)}))


def test_response_helpers():
    request = parse(raw())
    assert json.loads(ok_response(request, {"a": 1}).to_json())["payload"] == {"ok": True, "a": 1}
    err = json.loads(error_response(request, "unsupported").to_json())
    assert err["payload"]["ok"] is False and err["id"] == "1" and err["kind"] == "res"
