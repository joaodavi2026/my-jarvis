from __future__ import annotations

import asyncio
import json
import logging

import pytest
from websockets.asyncio.client import connect
from websockets.exceptions import ConnectionClosed, InvalidStatus

from jarvis.core.events import Event
from jarvis.ipc.allowlists import inbound_allowed
from jarvis.ipc.server import IpcServer, OutboundQueue

from .conftest import evt, open_authenticated, req, uri


async def closed_code(ws) -> int:
    with pytest.raises(ConnectionClosed) as info:
        await asyncio.wait_for(ws.recv(), 3)
    return info.value.rcvd.code


async def test_binds_to_loopback_only(server):
    assert server.bound_addresses == ["127.0.0.1"]
    assert server.port > 0


def test_short_token_is_refused(bus):
    with pytest.raises(ValueError):
        IpcServer("short", bus)


async def test_valid_hello_then_ping(server, token):
    ws = await open_authenticated(server, token)
    await ws.send(req("ping", "p1"))
    reply = json.loads(await ws.recv())
    assert reply["kind"] == "res" and reply["id"] == "p1" and reply["payload"] == {"ok": True}
    await ws.close()


BAD_FIRST_MESSAGES = [
    lambda token: req("hello", "h", token="x" * 64),
    lambda token: req("hello", "h"),
    lambda token: req("ping", "h", token="whatever"),
    lambda token: evt("hello", token="whatever"),
    lambda token: "this is not json",
    lambda token: json.dumps([1, 2, 3]),
]


@pytest.mark.parametrize("first_message", BAD_FIRST_MESSAGES)
async def test_bad_first_message_closes_with_4401(server, token, first_message):
    ws = await connect(uri(server))
    await ws.send(first_message(token))
    assert await closed_code(ws) == 4401


async def test_silent_client_times_out_with_4401(server):
    ws = await connect(uri(server))
    assert await closed_code(ws) == 4401


async def test_browser_origin_is_rejected(server):
    with pytest.raises(InvalidStatus) as info:
        await connect(uri(server), origin="http://evil.example")
    assert info.value.response.status_code == 403


async def test_foreign_host_header_is_rejected(server):
    with pytest.raises(InvalidStatus) as info:
        await connect(uri(server), additional_headers={"Host": "evil.example"})
    assert info.value.response.status_code == 403


async def test_single_connection_at_a_time(server, token):
    first = await open_authenticated(server, token)
    second = await connect(uri(server))
    assert await closed_code(second) == 4409
    await first.close()
    await asyncio.sleep(0.1)
    third = await open_authenticated(server, token)
    await third.close()


async def test_unauthenticated_client_gets_no_events(server, token, bus):
    ws = await connect(uri(server))
    bus.publish("state.changed", {"state": "IDLE"})
    await ws.send(req("hello", "h", token="x" * 64))
    assert await closed_code(ws) == 4401


async def test_only_allow_listed_events_reach_the_client(server, token, bus):
    ws = await open_authenticated(server, token)
    bus.publish("router.matched", {"intent": "internal-only"})
    bus.publish("storage.removed", {"detail": "internal"})
    bus.publish("state.changed", {"state": "LISTENING"})
    first = json.loads(await asyncio.wait_for(ws.recv(), 2))
    assert first["kind"] == "evt" and first["type"] == "state.changed"
    await ws.send(req("ping", "barrier"))
    following = json.loads(await asyncio.wait_for(ws.recv(), 2))
    assert following["id"] == "barrier"


async def test_client_cannot_forge_internal_events(server, token, bus):
    seen: list[str] = []
    bus.subscribe("*", lambda e: seen.append(e.type))
    ws = await open_authenticated(server, token)
    for forged in ("state.changed", "tool.completed", "confirmation.requested", "permission.evaluated"):
        await ws.send(evt(forged, state="IDLE"))
    await ws.send(evt("shell.window_moved", x=1))
    await ws.send(evt("activation.orb_clicked"))
    await ws.send(evt("confirmation.answered", id="c1", approved=True))
    await ws.send(req("ping", "barrier"))
    await asyncio.wait_for(ws.recv(), 2)
    published = [t for t in seen if not t.startswith("ipc.")]
    assert published == ["shell.window_moved", "activation.orb_clicked", "confirmation.answered"]


def test_inbound_allow_list():
    assert inbound_allowed("shell.menu_action") and inbound_allowed("activation.cancelled")
    assert not inbound_allowed("state.changed") and not inbound_allowed("tool.started")
    assert not inbound_allowed("shellx.thing")


async def test_unknown_request_gets_unsupported_error(server, token):
    ws = await open_authenticated(server, token)
    await ws.send(req("danger.run", "d1"))
    reply = json.loads(await ws.recv())
    assert reply["payload"]["ok"] is False and reply["payload"]["error"] == "unsupported"


async def test_handler_exception_becomes_internal_error_without_crashing(server, token):
    def broken(_request):
        raise RuntimeError("secret internal detail")

    server.register("broken", broken)
    ws = await open_authenticated(server, token)
    await ws.send(req("broken", "b1"))
    reply = json.loads(await ws.recv())
    assert reply["payload"]["error"] == "internal" and "secret" not in json.dumps(reply)
    await ws.send(req("ping", "after"))
    assert json.loads(await ws.recv())["payload"]["ok"] is True


async def test_malformed_message_after_auth_closes_connection(server, token):
    ws = await open_authenticated(server, token)
    await ws.send("{broken")
    assert await closed_code(ws) == 1008


async def test_oversized_message_closes_with_1009(server, token):
    ws = await open_authenticated(server, token)
    await ws.send("x" * (2 * 1024 * 1024))
    assert await closed_code(ws) == 1009


async def test_token_is_never_logged(server, token, caplog):
    caplog.set_level(logging.DEBUG)
    bad = await connect(uri(server))
    await bad.send(req("hello", "h", token="y" * 64))
    await closed_code(bad)
    good = await open_authenticated(server, token)
    await good.close()
    await asyncio.sleep(0.1)
    assert token not in caplog.text and "y" * 64 not in caplog.text


def test_outbound_queue_drops_droppable_events_first():
    queue = OutboundQueue(limit=3)
    queue.put(Event("audio.level"))
    queue.put(Event("state.changed"))
    queue.put(Event("audio.level"))
    queue.put(Event("tool.started"))
    assert queue.dropped == 1
    assert [e.type for e in queue._items] == ["state.changed", "audio.level", "tool.started"]
    queue.put(Event("tool.completed"))
    queue.put(Event("error.occurred"))
    assert [e.type for e in queue._items] == ["tool.started", "tool.completed", "error.occurred"]
