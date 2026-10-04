import { describe, expect, it } from "vitest";
import spec from "../../../contracts/state-machine.json";
import { ALL_STATES, INITIAL_STATE, transition } from "./machine";

describe("interaction state machine (driven by contracts/state-machine.json)", () => {
  it("starts in BOOTING and every declared state is known to the table", () => {
    expect(INITIAL_STATE).toBe("BOOTING");
    for (const t of spec.transitions) {
      expect(ALL_STATES).toContain(t.from);
      expect(ALL_STATES).toContain(t.to);
    }
  });

  it("follows every transition declared in the contract", () => {
    for (const t of spec.transitions) {
      expect(transition(t.from as never, t.on)).toBe(t.to);
    }
  });

  it("runs the canonical voice-command flow", () => {
    const steps: [string, string][] = [
      ["activation_requested", "ACTIVATED"],
      ["listening_started", "LISTENING"],
      ["transcription_ready", "PROCESSING"],
      ["tool_started", "EXECUTING"],
      ["tool_completed", "PROCESSING"],
      ["response_ready", "SPEAKING"],
      ["speech_finished", "IDLE"],
    ];
    let state = "IDLE" as never;
    for (const [trigger, expected] of steps) {
      state = transition(state, trigger) as never;
      expect(state).toBe(expected);
    }
  });

  it("rejects triggers that are not valid from the current state", () => {
    expect(transition("IDLE", "speech_finished")).toBeNull();
    expect(transition("LISTENING", "activation_requested")).toBeNull();
    expect(transition("SPEAKING", "tool_started")).toBeNull();
    expect(transition("IDLE", "no_such_trigger")).toBeNull();
  });

  it("allows cancellation exactly from the cancellable states", () => {
    for (const state of ALL_STATES) {
      const expected = (spec.cancellable_from as string[]).includes(state) ? "CANCELLED" : null;
      expect(transition(state, "cancel_requested")).toBe(expected);
    }
    expect(transition("CANCELLED", "cancel_completed")).toBe("IDLE");
  });

  it("fails into ERROR from anywhere except BOOTING, and goes OFFLINE when the service is lost", () => {
    for (const state of ALL_STATES) {
      expect(transition(state, "failure")).toBe(state === "BOOTING" ? null : "ERROR");
      expect(transition(state, "service_lost")).toBe("OFFLINE");
    }
    expect(transition("OFFLINE", "service_restored")).toBe("IDLE");
  });

  it("supports barge-in: speaking can return to listening", () => {
    expect(transition("SPEAKING", "barge_in")).toBe("LISTENING");
  });

  it("every non-initial state is reachable from BOOTING", () => {
    const seen = new Set<string>([INITIAL_STATE]);
    const queue = [INITIAL_STATE as string];
    const triggers = new Set<string>([...spec.transitions.map((t) => t.on), "cancel_requested", "failure", "service_lost"]);
    while (queue.length) {
      const current = queue.shift()!;
      for (const trigger of triggers) {
        const next = transition(current as never, trigger);
        if (next && !seen.has(next)) {
          seen.add(next);
          queue.push(next);
        }
      }
    }
    expect([...seen].sort()).toEqual([...ALL_STATES].sort());
  });
});
