"""Applies JARVIS_MIC, then hands over to the native OpenJarvis voice chat (jarvis chat --voice)."""

from __future__ import annotations

import os

from .devices import resolve_device


def main() -> int:
    import sounddevice as sd

    spec = os.environ.get("JARVIS_MIC", "").strip() or None
    try:
        device = resolve_device(spec, list(sd.query_devices()))
    except ValueError as exc:
        print("JARVIS_MIC: %s. Run: jarvis-show --list-devices" % exc)
        return 2
    if device is not None:
        sd.default.device = (device, sd.default.device[1])
    from openjarvis.cli import main as jarvis_main

    jarvis_main(args=["chat", "--voice"], prog_name="jarvis", standalone_mode=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
