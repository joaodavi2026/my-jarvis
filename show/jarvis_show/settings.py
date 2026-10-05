"""Settings from environment variables, so nobody has to edit Python to change the microphone or sensitivity."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_THRESH = 8.0


def _float(value: str | None, default: float) -> float:
    try:
        parsed = float(value) if value not in (None, "") else default
    except ValueError:
        return default
    return parsed if parsed > 0 else default


@dataclass(frozen=True)
class Settings:
    clap_thresh: float
    mic: str | None  # device index or part of the device name; None = Windows default input
    openjarvis_dir: Path
    url: str
    ollama_url: str
    jingle: Path | None

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None, show_dir: Path | None = None) -> "Settings":
        env = dict(os.environ if env is None else env)
        show_dir = show_dir or Path(__file__).resolve().parents[1]
        default_oj = show_dir.parent.parent / "jarvis"  # sibling checkout: <Source>/jarvis next to <Source>/my-jarvis
        jingle = find_jingle(env.get("JARVIS_JINGLE"), show_dir)
        return cls(
            clap_thresh=_float(env.get("JARVIS_CLAP_THRESH"), DEFAULT_THRESH),
            mic=(env.get("JARVIS_MIC") or "").strip() or None,
            openjarvis_dir=Path(env.get("JARVIS_OPENJARVIS_DIR") or default_oj),
            url=env.get("JARVIS_URL", "http://127.0.0.1:8000"),
            ollama_url=env.get("OLLAMA_HOST_URL", "http://127.0.0.1:11434"),
            jingle=jingle,
        )


def find_jingle(explicit: str | None, show_dir: Path) -> Path | None:
    """The jingle is optional. Existing user media is never overwritten or moved."""
    candidates = [Path(explicit)] if explicit else []
    candidates += [show_dir / "assets" / "jingle.mp3", show_dir.parent / "voz" / "assets" / "jingle.mp3"]
    return next((p for p in candidates if p.is_file()), None)
