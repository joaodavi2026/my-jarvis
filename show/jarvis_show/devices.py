"""Input device selection (JARVIS_MIC)."""

from __future__ import annotations

from typing import Any


def input_devices(devices: list[dict[str, Any]]) -> list[tuple[int, str]]:
    return [(i, d["name"]) for i, d in enumerate(devices) if d.get("max_input_channels", 0) > 0]


def resolve_device(spec: str | None, devices: list[dict[str, Any]]) -> int | None:
    """None -> the default input. An integer string -> that index. Otherwise a case-insensitive name fragment."""
    if not spec:
        return None
    inputs = input_devices(devices)
    if spec.isdigit():
        index = int(spec)
        if any(i == index for i, _ in inputs):
            return index
        raise ValueError("device index %d is not an input device" % index)
    matches = [i for i, name in inputs if spec.lower() in name.lower()]
    if not matches:
        raise ValueError("no input device matches %r" % spec)
    return matches[0]
