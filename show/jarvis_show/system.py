"""Real side effects for Windows (kept thin; the logic lives in orchestrator.py)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import webbrowser
from pathlib import Path

DETACHED = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP


def http_ok(url: str, timeout: float = 1.5) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:  # loopback only
            return 200 <= response.status < 500
    except Exception:
        return False


def _find(name: str, extra: list[Path]) -> str | None:
    return shutil.which(name) or next((str(p) for p in extra if p.is_file()), None)


def start_ollama() -> None:
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama"
    exe = _find("ollama", [local / "ollama.exe"])
    if exe:
        subprocess.Popen([exe, "serve"], creationflags=DETACHED, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def start_server(openjarvis_dir: Path) -> None:
    """uv run jarvis start, from the OpenJarvis checkout, detached, logging to a temp file (no console spam)."""
    uv = shutil.which("uv")
    if not uv:
        return
    log = open(Path(tempfile.gettempdir()) / "jarvis-server.log", "ab")
    subprocess.Popen([uv, "run", "jarvis", "start"], cwd=str(openjarvis_dir), creationflags=DETACHED, stdout=log, stderr=log)


def open_browser(url: str) -> None:
    webbrowser.open(url)


def start_voice_chat() -> None:
    """Opens the native OpenJarvis voice chat in its own console, through our shim (it applies JARVIS_MIC)."""
    quote = chr(34)
    cmd = quote + sys.executable + quote + " -m jarvis_show.voice_chat"
    subprocess.Popen(["cmd.exe", "/c", "start", "JARVIS", "cmd.exe", "/k", cmd], env=os.environ.copy())


def play_jingle(path: Path) -> None:
    """Plays the jingle (blocking, a few seconds). Needs numpy, sounddevice and soundfile (the voice extra)."""
    import sounddevice as sd
    import soundfile as sf

    data, rate = sf.read(str(path), dtype="float32")
    sd.play(data, rate)
    sd.wait()
