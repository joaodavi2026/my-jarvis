from __future__ import annotations

import asyncio

from jarvis.core.events import EventBus


async def test_exact_prefix_and_wildcard_subscriptions():
    bus = EventBus()
    seen: dict[str, list[str]] = {"exact": [], "prefix": [], "all": []}
    bus.subscribe("state.changed", lambda e: seen["exact"].append(e.type))
    bus.subscribe("storage.*", lambda e: seen["prefix"].append(e.type))
    bus.subscribe("*", lambda e: seen["all"].append(e.type))
    bus.publish("state.changed")
    bus.publish("storage.removed")
    bus.publish("storage.status_changed")
    bus.publish("storagefoo.x")
    assert seen["exact"] == ["state.changed"]
    assert seen["prefix"] == ["storage.removed", "storage.status_changed"]
    assert len(seen["all"]) == 4


async def test_failing_handlers_are_isolated():
    bus = EventBus()
    received = []

    def bad(event):
        raise RuntimeError("boom")

    async def bad_async(event):
        raise RuntimeError("async boom")

    bus.subscribe("x.y", bad)
    bus.subscribe("x.y", bad_async)
    bus.subscribe("x.y", lambda e: received.append(e.payload["n"]))
    bus.publish("x.y", {"n": 1})
    await bus.drain()
    assert received == [1]


async def test_async_handlers_run_and_unsubscribe_works():
    bus = EventBus()
    out = []

    async def handler(event):
        await asyncio.sleep(0)
        out.append(event.type)

    off = bus.subscribe("a.b", handler)
    bus.publish("a.b")
    await bus.drain()
    off()
    bus.publish("a.b")
    await bus.drain()
    assert out == ["a.b"]


async def test_payload_is_copied_and_correlation_id_kept():
    bus = EventBus()
    original = {"k": 1}
    event = bus.publish("t.e", original, correlation_id="run-1")
    original["k"] = 2
    assert event.payload == {"k": 1} and event.correlation_id == "run-1"
