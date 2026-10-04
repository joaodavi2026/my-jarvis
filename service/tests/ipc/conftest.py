from __future__ import annotations

import json
import secrets

import pytest
from websockets.asyncio.client import connect

from jarvis.core.events import EventBus
from jarvis.ipc.server import IpcServer


@pytest.fixture
def token() -> str:
    return secrets.token_hex(32)


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


@pytest.fixture
async def server(token, bus):
    srv = IpcServer(token, bus, handshake_timeout=0.5, queue_limit=64, ping_interval=None)
    await srv.start()
    yield srv
    await srv.stop()


def uri(server: IpcServer) -> str:
    return f"ws://127.0.0.1:{server.port}/"


def req(type_: str, id_: str = "1", **payload) -> str:
    return json.dumps({"v": 1, "kind": "req", "id": id_, "type": type_, "payload": payload})


def evt(type_: str, **payload) -> str:
    return json.dumps({"v": 1, "kind": "evt", "type": type_, "payload": payload})


async def open_authenticated(server: IpcServer, token: str, **kwargs):
    ws = await connect(uri(server), **kwargs)
    await ws.send(req("hello", "h", token=token))
    reply = json.loads(await ws.recv())
    assert reply["payload"]["ok"] is True, reply
    return ws
