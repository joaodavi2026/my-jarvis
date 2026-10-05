"""What happens after the double clap: jingle -> Ollama -> OpenJarvis server -> browser (once) -> voice chat.

Every side effect is injected, so the sequence is unit-tested without audio, network or processes.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger("jarvis_show")


@dataclass
class Actions:
    play_jingle: Callable[[Path], None]
    http_ok: Callable[[str], bool]
    start_ollama: Callable[[], None]
    start_server: Callable[[], None]
    open_browser: Callable[[str], bool]  # returns False when it deliberately did not open a tab
    start_voice_chat: Callable[[], None] | None  # None = normal mode (no voice chat)
    sleep: Callable[[float], None] = time.sleep
    now: Callable[[], float] = time.monotonic


@dataclass
class Orchestrator:
    jingle: Path | None
    url: str
    ollama_url: str
    actions: Actions
    open_browser: bool = True
    browser_debounce_s: float = 120.0
    wait_s: float = 45.0
    _last_browser: float = field(default=-1e9, init=False)

    def activate(self) -> list[str]:
        """Runs the whole sequence and returns the steps taken. A failing step never aborts the rest, unless the rest
        cannot work without it (the voice chat needs the Ollama backend)."""
        steps: list[str] = []
        a = self.actions
        if self.jingle is not None:
            try:
                a.play_jingle(self.jingle)
                steps.append("jingle")
            except Exception as exc:  # the jingle is decoration, never a dependency
                log.warning("jingle failed: %s", type(exc).__name__)
                steps.append("jingle_failed")
        else:
            steps.append("no_jingle")

        if not self._ensure(self.ollama_url + "/api/version", a.start_ollama):
            steps.append("ollama_unavailable")
            return steps
        steps.append("ollama_ok")

        if self._ensure(self.url, a.start_server):
            steps.append("server_ok")
            if self.open_browser and a.now() - self._last_browser >= self.browser_debounce_s:
                self._last_browser = a.now()
                steps.append("browser" if a.open_browser(self.url) else "browser_skipped")
        else:
            steps.append("server_unavailable")  # the voice chat still works without the web UI

        if a.start_voice_chat is not None:
            a.start_voice_chat()
            steps.append("voice_chat")
        return steps

    def _ensure(self, url: str, start: Callable[[], None]) -> bool:
        a = self.actions
        if a.http_ok(url):
            return True
        start()
        deadline = a.now() + self.wait_s
        while a.now() < deadline:
            if a.http_ok(url):
                return True
            a.sleep(0.5)
        return False
