from __future__ import annotations

import json
from itertools import product

import pytest

from jarvis.core.state import InteractionMachine, default_contract_path

SPEC = json.loads(default_contract_path().read_text(encoding="utf-8"))
STATES = SPEC["states"]
TRIGGERS = sorted({t["on"] for t in SPEC["transitions"]} | {"cancel_requested", "failure", "service_lost", "bogus"})


def machine_in(state: str) -> InteractionMachine:
    machine = InteractionMachine(SPEC)
    machine._state = state  # direct placement: the table, not the path, is under test here
    return machine


def test_starts_in_booting():
    assert InteractionMachine(SPEC).state == "BOOTING"


@pytest.mark.parametrize("transition", SPEC["transitions"], ids=lambda t: f"{t['from']}-{t['on']}")
def test_every_declared_transition_is_followed(transition):
    machine = machine_in(transition["from"])
    assert machine.dispatch(transition["on"])
    assert machine.state == transition["to"]


def test_undeclared_triggers_are_rejected_without_changing_state():
    declared = {(t["from"], t["on"]) for t in SPEC["transitions"]}
    for state, trigger in product(STATES, TRIGGERS):
        if trigger in ("cancel_requested", "failure", "service_lost") or (state, trigger) in declared:
            continue
        machine = machine_in(state)
        assert not machine.dispatch(trigger)
        assert machine.state == state


def test_global_triggers_follow_the_contract():
    for state in STATES:
        cancel = machine_in(state)
        assert cancel.dispatch("cancel_requested") == (state in SPEC["cancellable_from"])
        failing = machine_in(state)
        assert failing.dispatch("failure") == (state != "BOOTING")
        lost = machine_in(state)
        assert lost.dispatch("service_lost") and lost.state == "OFFLINE"


def test_canonical_flow_and_change_notifications():
    changes = []
    machine = InteractionMachine(SPEC, on_change=lambda prev, new, trig: changes.append((prev, new, trig)))
    for trigger in ["boot_completed", "activation_requested", "listening_started", "transcription_ready",
                    "tool_started", "tool_completed", "response_ready", "speech_finished"]:
        assert machine.dispatch(trigger), trigger
    assert machine.state == "IDLE"
    assert changes[0] == ("BOOTING", "IDLE", "boot_completed")
    assert [c[1] for c in changes] == ["IDLE", "ACTIVATED", "LISTENING", "PROCESSING", "EXECUTING",
                                       "PROCESSING", "SPEAKING", "IDLE"]


def test_rejects_unsupported_contract_version():
    with pytest.raises(ValueError):
        InteractionMachine({**SPEC, "version": 99})
