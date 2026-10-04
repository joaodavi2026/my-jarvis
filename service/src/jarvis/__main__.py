"""Service entry point: python -m jarvis

Bootstrap protocol with the Rust shell (contracts/protocol.md):
  1. the shell writes the session token as the first line on stdin and keeps stdin open;
  2. the service prints one JSON line on stdout once the IPC server is listening (never the token);
  3. when stdin reaches EOF (the shell exited or closed it) the service shuts down.
Logs go to stderr only.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import threading

from .app import ServiceApp
from .paths import default_internal_root
from .storage.windows_volumes import WindowsVolumeProvider

log = logging.getLogger("jarvis")


def _watch_stdin(loop: asyncio.AbstractEventLoop, stop: asyncio.Event) -> None:
    def run() -> None:
        try:
            while sys.stdin.readline():
                pass
        finally:
            loop.call_soon_threadsafe(stop.set)

    threading.Thread(target=run, name="stdin-watch", daemon=True).start()


async def amain() -> int:
    token = (await asyncio.get_running_loop().run_in_executor(None, sys.stdin.readline)).strip()
    if len(token) < 32:
        log.error("missing or too short session token on stdin")
        return 2
    app = ServiceApp(token=token, internal_root=default_internal_root(), provider=WindowsVolumeProvider())
    stop = asyncio.Event()
    _watch_stdin(asyncio.get_running_loop(), stop)
    port = await app.start()
    sys.stdout.write(json.dumps({"ready": True, "port": port, "protocol": 1}) + "\n")
    sys.stdout.flush()
    log.info("service ready on 127.0.0.1:%d", port)
    await stop.wait()
    await app.stop()
    return 0


def main() -> int:
    logging.basicConfig(stream=sys.stderr, level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        return asyncio.run(amain())
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
