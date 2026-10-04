import { describe, expect, it } from "vitest";
import { toAction } from "./events";

describe("toAction", () => {
  it("maps state.changed with a substage", () => {
    expect(toAction({ type: "state.changed", payload: { state: "PROCESSING", substage: "COMPOSING" } })).toEqual({
      type: "backend_state",
      state: "PROCESSING",
      substage: "COMPOSING",
      label: undefined,
    });
  });

  it("rejects unknown states and malformed payloads instead of trusting them", () => {
    expect(toAction({ type: "state.changed", payload: { state: "HACKED" } })).toBeNull();
    expect(toAction({ type: "state.changed" })).toBeNull();
    expect(toAction({ type: "audio.level", payload: { level: "loud" } })).toBeNull();
    expect(toAction({ type: "audio.level", payload: { level: Number.NaN } })).toBeNull();
    expect(toAction({ type: "feedback.pulse", payload: { kind: "BOOM" } })).toBeNull();
    expect(toAction({ type: "service.status", payload: { status: "MAYBE" } })).toBeNull();
  });

  it("maps level, privacy, storage, pulse and service events", () => {
    expect(toAction({ type: "audio.level", payload: { level: 0.4 } })).toEqual({ type: "level", level: 0.4 });
    expect(toAction({ type: "privacy.changed", payload: { microphone: true, camera: "x" } })).toEqual({
      type: "privacy",
      privacy: { microphone: true },
    });
    expect(toAction({ type: "storage.status_changed", payload: { mode: "DEGRADED" } })).toEqual({ type: "storage", degraded: true });
    expect(toAction({ type: "feedback.pulse", payload: { kind: "SUCCESS" } })).toEqual({ type: "pulse", pulse: "SUCCESS" });
    expect(toAction({ type: "service.status", payload: { status: "DOWN" } })).toEqual({ type: "service", status: "DOWN" });
  });

  it("ignores events the UI does not render", () => {
    expect(toAction({ type: "router.matched" })).toBeNull();
  });
});
