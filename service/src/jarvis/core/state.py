"""Authoritative interaction state machine. The transition table is contracts/state-machine.json."""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from pathlib import Path

log = logging.getLogger(__name__)

StateListener = Callable[[str, str, str], None]  # (previous, new, trigger)


def default_contract_path() -> Path:
    """Dev layout: <repo>/contracts/state-machine.json (an installed build bundles this file)."""
    return Path(__file__).resolve().parents[4] / "contracts" / "state-machine.json"


class InteractionMachine:
    def __init__(self, spec: dict, on_change: StateListener | None = None) -> None:
        if spec.get("version") != 1:
            raise ValueError("unsupported state machine contract version")
        self.states: list[str] = list(spec["states"])
        self._table = {(t["from"], t["on"]): t["to"] for t in spec["transitions"]}
        self._cancellable = set(spec["cancellable_from"])
        self._state: str = spec["initial"]
        self._on_change = on_change

    @classmethod
    def from_file(cls, path: Path | None = None, on_change: StateListener | None = None) -> "InteractionMachine":
        return cls(json.loads((path or default_contract_path()).read_text(encoding="utf-8")), on_change)

    @property
    def state(self) -> str:
        return self._state

    def next_state(self, trigger: str) -> str | None:
        """Pure lookup: the state `trigger` leads to from the current state, or None if invalid."""
        if trigger == "cancel_requested":
            return "CANCELLED" if self._state in self._cancellable else None
        if trigger == "failure":
            return None if self._state == "BOOTING" else "ERROR"
        if trigger == "service_lost":
            return "OFFLINE"
        return self._table.get((self._state, trigger))

    def dispatch(self, trigger: str) -> bool:
        """Applies a trigger. Invalid triggers are rejected (logged), never forced."""
        target = self.next_state(trigger)
        if target is None:
            log.warning("rejected trigger %s in state %s", trigger, self._state)
            return False
        previous, self._state = self._state, target
        if self._on_change:
            self._on_change(previous, target, trigger)
        return True
