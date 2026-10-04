"""Authenticated loopback WebSocket server (ADR-0002).

Security properties enforced here:
  * binds to 127.0.0.1 only, on an ephemeral port
  * the first message must be hello{token} within the handshake timeout (constant-time compare)
  * connections carrying an Origin header (browsers) or a foreign Host header are rejected
  * a single authenticated connection at a time
  * incoming events are restricted to an allow-list; unknown requests get an error response
  * the token is never logged
"""

from __future__ import annotations

import asyncio
import contextlib
import hmac
import logging
from collections import deque
from collections.abc import Awaitable, Callable
from http import HTTPStatus
from typing import Any

from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.exceptions import ConnectionClosed
from websockets.http11 import Request, Response

from ..core.events import Event, EventBus
from .allowlists import DROPPABLE_TYPES, OUTBOUND_TYPES, inbound_allowed
from .protocol import (CLOSE_BUSY, CLOSE_UNAUTHORIZED, MAX_MESSAGE_BYTES, Envelope, ProtocolError,
                       error_response, ok_response, parse)

log = logging.getLogger(__name__)

RequestHandler = Callable[[Envelope], Awaitable[dict[str, Any]] | dict[str, Any]]
HOST = "127.0.0.1"
MIN_TOKEN_LENGTH = 32


class OutboundQueue:
    """Bounded queue: when full, the oldest droppable event goes first, then the oldest of all."""

    def __init__(self, limit: int = 256) -> None:
        self._items: deque[Event] = deque()
        self._limit = limit
        self._ready = asyncio.Event()
        self.dropped = 0

    def put(self, event: Event) -> None:
        if len(self._items) >= self._limit:
            victim = next((e for e in self._items if e.type in DROPPABLE_TYPES), None)
            if victim is not None:
                self._items.remove(victim)
            else:
                self._items.popleft()
            self.dropped += 1
        self._items.append(event)
        self._ready.set()

    async def get(self) -> Event:
        while not self._items:
            self._ready.clear()
            await self._ready.wait()
        return self._items.popleft()


class IpcServer:
    def __init__(self, token: str, bus: EventBus, *, port: int = 0, handshake_timeout: float = 2.0,
                 queue_limit: int = 256, ping_interval: float | None = 10.0) -> None:
        if len(token) < MIN_TOKEN_LENGTH:
            raise ValueError("session token too short")
        self._token = token.encode("utf-8")
        self._bus = bus
        self._requested_port = port
        self._handshake_timeout = handshake_timeout
        self._queue_limit = queue_limit
        self._ping_interval = ping_interval
        self._handlers: dict[str, RequestHandler] = {"ping": lambda _request: {}}
        self._server: Server | None = None
        self._active: ServerConnection | None = None
        self._unsubscribe: Callable[[], None] | None = None
        self.port = 0

    def register(self, request_type: str, handler: RequestHandler) -> None:
        self._handlers[request_type] = handler

    @property
    def connected(self) -> bool:
        return self._active is not None

    async def start(self) -> int:
        self._server = await serve(
            self._on_connection, HOST, self._requested_port, max_size=MAX_MESSAGE_BYTES,
            process_request=self._check_request, ping_interval=self._ping_interval,
            ping_timeout=30 if self._ping_interval else None,
        )
        self.port = self._server.sockets[0].getsockname()[1]
        return self.port

    @property
    def bound_addresses(self) -> list[str]:
        return [s.getsockname()[0] for s in (self._server.sockets if self._server else [])]

    async def stop(self) -> None:
        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()
            self._server = None

    # ── connection admission ───────────────────────────────────────
    def _check_request(self, connection: ServerConnection, request: Request) -> Response | None:
        headers = request.headers
        if headers.get("Origin") is not None:  # browsers always send Origin; the shell never does
            return connection.respond(HTTPStatus.FORBIDDEN, "forbidden")
        hosts = headers.get_all("Host")  # exactly one Host header, and it must be loopback
        if len(hosts) != 1 or hosts[0].rsplit(":", 1)[0] not in (HOST, "localhost"):
            return connection.respond(HTTPStatus.FORBIDDEN, "forbidden")
        return None

    async def _on_connection(self, ws: ServerConnection) -> None:
        if self._active is not None:
            await ws.close(CLOSE_BUSY, "busy")
            return
        self._active = ws  # reserve immediately so a second client cannot race the handshake
        try:
            if not await self._authenticate(ws):
                return
            await self._serve_client(ws)
        except ConnectionClosed:
            pass
        finally:
            self._active = None
            if self._unsubscribe:
                self._unsubscribe()
                self._unsubscribe = None

    async def _authenticate(self, ws: ServerConnection) -> bool:
        try:
            raw = await asyncio.wait_for(ws.recv(), self._handshake_timeout)
            hello = parse(raw)
        except (asyncio.TimeoutError, ProtocolError):
            await ws.close(CLOSE_UNAUTHORIZED, "unauthorized")
            return False
        supplied = str(hello.payload.get("token", "")).encode("utf-8")
        if hello.kind != "req" or hello.type != "hello" or not hmac.compare_digest(supplied, self._token):
            await ws.close(CLOSE_UNAUTHORIZED, "unauthorized")
            log.warning("rejected unauthenticated IPC client")
            return False
        await ws.send(ok_response(hello, {"server": "jarvis-service", "protocol": 1}).to_json())
        return True

    # ── authenticated session ──────────────────────────────────────
    async def _serve_client(self, ws: ServerConnection) -> None:
        queue = OutboundQueue(self._queue_limit)

        def forward(event: Event) -> None:
            if event.type in OUTBOUND_TYPES:
                queue.put(event)

        self._unsubscribe = self._bus.subscribe("*", forward)
        self._bus.publish("ipc.client_connected")
        sender = asyncio.create_task(self._pump_outbound(ws, queue))
        try:
            async for raw in ws:
                await self._handle_message(ws, raw)
        finally:
            sender.cancel()
            with contextlib.suppress(asyncio.CancelledError, ConnectionClosed):
                await sender
            self._bus.publish("ipc.client_disconnected")

    @staticmethod
    async def _pump_outbound(ws: ServerConnection, queue: OutboundQueue) -> None:
        while True:
            event = await queue.get()
            await ws.send(Envelope("evt", event.type, event.payload).to_json())

    async def _handle_message(self, ws: ServerConnection, raw: str | bytes) -> None:
        try:
            message = parse(raw)
        except ProtocolError as exc:
            log.warning("invalid IPC message: %s", exc)
            await ws.close(1008, "protocol error")
            return
        if message.kind == "evt":
            if inbound_allowed(message.type):
                self._bus.publish(message.type, message.payload)
            else:
                log.warning("dropped disallowed inbound event %s", message.type)
            return
        if message.kind != "req":
            return
        handler = self._handlers.get(message.type)
        if handler is None:
            await ws.send(error_response(message, "unsupported").to_json())
            return
        try:
            result = handler(message)
            if asyncio.iscoroutine(result):
                result = await result
            await ws.send(ok_response(message, result).to_json())
        except Exception:
            log.exception("IPC request handler failed: %s", message.type)
            await ws.send(error_response(message, "internal").to_json())
