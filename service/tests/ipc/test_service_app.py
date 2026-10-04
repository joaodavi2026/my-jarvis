from __future__ import annotations

import asyncio
import json
import os
import secrets
import sys
from pathlib import Path

import pytest
from websockets.asyncio.client import connect

from jarvis.app import ServiceApp
from jarvis.storage import StorageConfig, save_storage_config
from jarvis.storage.config import ExternalIdentity

from ..storage.fakes import HD_GUID, FakeVolumeProvider
from .conftest import evt, open_authenticated, req, uri

SRC = str(Path(__file__).resolve().parents[2] / "src")


@pytest.fixture
async def running(tmp_path):
    token = secrets.token_hex(32)
    internal = tmp_path / "ssd"
    provider = FakeVolumeProvider()
    disk = tmp_path / "hd"
    provider.add(HD_GUID, "HD JD", "Q:", disk)
    (disk / "JARVIS").mkdir()
    save_storage_config(internal / "config" / "config.json",
                        StorageConfig(ExternalIdentity(volume_guid=HD_GUID, preferred_drive="Q:")))
    app = ServiceApp(token=token, internal_root=internal, provider=provider, monitor_interval=0.05)
    await app.start()
    yield app, token, provider, disk
    await app.stop()


async def request(ws, type_: str, id_: str = "r") -> dict:
    await ws.send(req(type_, id_))
    while True:
        message = json.loads(await asyncio.wait_for(ws.recv(), 3))
        if message["kind"] == "res" and message["id"] == id_:
            return message["payload"]


async def next_event(ws, type_: str) -> dict:
    while True:
        message = json.loads(await asyncio.wait_for(ws.recv(), 3))
        if message["kind"] == "evt" and message["type"] == type_:
            return message["payload"]


async def test_boots_to_idle_and_reports_honest_health(running):
    app, token, _provider, _disk = running
    assert app.machine.state == "IDLE"
    ws = await open_authenticated(app.ipc, token)
    assert (await request(ws, "state.get"))["state"] == "IDLE"
    health = await request(ws, "health.get")
    assert health["capabilities"]["storage"]["status"] == "AVAILABLE"
    assert health["capabilities"]["ipc"]["client_connected"] is True
    for planned in ("audio", "stt", "tts", "local_ai", "tools"):
        assert health["capabilities"][planned] == {"status": "UNAVAILABLE", "reason": "not_implemented"}


async def test_orb_click_without_audio_reports_error_instead_of_pretending_to_listen(running):
    app, token, _provider, _disk = running
    ws = await open_authenticated(app.ipc, token)
    await ws.send(evt("activation.orb_clicked"))
    error = await next_event(ws, "error.occurred")
    assert error["code"] == "audio_unavailable"
    assert (await next_event(ws, "feedback.pulse"))["kind"] == "ERROR"
    assert app.machine.state == "IDLE"


async def test_cancel_in_idle_changes_nothing(running):
    app, token, _provider, _disk = running
    ws = await open_authenticated(app.ipc, token)
    await ws.send(evt("activation.cancelled", source="orb"))
    assert (await request(ws, "state.get"))["state"] == "IDLE"


async def test_cancel_while_active_returns_to_idle(running):
    app, token, _provider, _disk = running
    for trigger in ("activation_requested", "listening_started"):
        app.machine.dispatch(trigger)
    ws = await open_authenticated(app.ipc, token)
    await ws.send(evt("activation.cancelled", source="orb"))
    state = await next_event(ws, "state.changed")
    assert state["state"] == "CANCELLED"
    assert (await next_event(ws, "state.changed"))["state"] == "IDLE"


async def test_storage_removal_and_return_reach_the_client(running):
    app, token, provider, disk = running
    ws = await open_authenticated(app.ipc, token)
    provider.remove(HD_GUID)
    degraded = await next_event(ws, "storage.status_changed")
    assert degraded["mode"] == "DEGRADED"
    assert (await request(ws, "health.get"))["capabilities"]["storage"]["status"] == "DEGRADED"
    provider.add(HD_GUID, "HD JD", "Q:", disk)
    while (await next_event(ws, "storage.status_changed"))["mode"] != "NORMAL":
        pass
    assert (await request(ws, "storage.get"))["mode"] == "NORMAL"


def _env(tmp_path: Path) -> dict[str, str]:
    env = dict(os.environ)
    env.update({"PYTHONPATH": SRC, "JARVIS_INTERNAL_ROOT": str(tmp_path / "internal")})
    return env


async def _spawn(tmp_path: Path):
    return await asyncio.create_subprocess_exec(
        sys.executable, "-m", "jarvis", stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, env=_env(tmp_path),
    )


async def test_real_process_bootstrap_protocol(tmp_path):
    """Exactly what the Rust shell does: token on stdin, ready line on stdout, EOF = shutdown."""
    token = secrets.token_hex(32)
    proc = await _spawn(tmp_path)
    try:
        proc.stdin.write((token + "\n").encode())
        await proc.stdin.drain()
        ready = json.loads(await asyncio.wait_for(proc.stdout.readline(), 15))
        assert ready["ready"] is True and ready["protocol"] == 1 and ready["port"] > 0
        assert token not in json.dumps(ready)

        ws = await connect(f"ws://127.0.0.1:{ready['port']}/")
        await ws.send(req("hello", "h", token=token))
        assert json.loads(await ws.recv())["payload"]["ok"] is True
        assert (await request(ws, "state.get"))["state"] == "IDLE"
        await ws.close()

        proc.stdin.close()  # the shell exiting closes stdin: the service must stop by itself
        assert await asyncio.wait_for(proc.wait(), 10) == 0
        out = (await proc.stdout.read()).decode()
        err = (await proc.stderr.read()).decode()
        assert token not in out and token not in err
        assert out.strip() == ""  # stdout carries only the ready line
    finally:
        if proc.returncode is None:
            proc.kill()


async def test_real_process_rejects_bad_tokens_and_exits_when_none_given(tmp_path):
    proc = await _spawn(tmp_path)
    proc.stdin.write(b"too-short\n")
    await proc.stdin.drain()
    assert await asyncio.wait_for(proc.wait(), 10) == 2
