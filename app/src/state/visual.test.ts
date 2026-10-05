import { describe, expect, it } from "vitest";
import { clickAction, deriveVisual, initialModel } from "./visual";
import type { AppModel, VisualState } from "./visual";
import { reducer } from "./store";

const connected = (over: Partial<AppModel>): AppModel => ({ ...initialModel, service: "CONNECTED", ...over });

describe("deriveVisual", () => {
  it("shows STARTING while connecting and OFFLINE when the service is down", () => {
    expect(deriveVisual(initialModel)).toBe("STARTING");
    expect(deriveVisual({ ...initialModel, service: "DOWN" })).toBe("OFFLINE");
  });

  it("maps every interaction state to the expected visual state", () => {
    const expected: Record<string, VisualState> = {
      BOOTING: "STARTING",
      IDLE: "IDLE",
      ACTIVATED: "LISTENING",
      LISTENING: "LISTENING",
      PROCESSING: "THINKING",
      EXECUTING: "EXECUTING",
      AWAITING_CONFIRMATION: "AWAITING",
      SPEAKING: "SPEAKING",
      CANCELLED: "IDLE",
      ERROR: "ERROR",
      OFFLINE: "OFFLINE",
    };
    for (const [state, visual] of Object.entries(expected)) {
      expect(deriveVisual(connected({ interaction: state as never }))).toBe(visual);
    }
  });

  it("pulses only overlay IDLE, never an active state", () => {
    expect(deriveVisual(connected({ interaction: "IDLE", pulse: "SUCCESS" }))).toBe("SUCCESS");
    expect(deriveVisual(connected({ interaction: "IDLE", pulse: "ERROR" }))).toBe("ERROR");
    expect(deriveVisual(connected({ interaction: "SPEAKING", pulse: "SUCCESS" }))).toBe("SPEAKING");
  });

  it("a lost service wins over any interaction state (the UI never pretends)", () => {
    expect(deriveVisual({ ...initialModel, service: "DOWN", interaction: "LISTENING" })).toBe("OFFLINE");
  });

  it("the simulator ignores service status", () => {
    expect(deriveVisual({ ...initialModel, source: "simulated", service: "DOWN", interaction: "IDLE" })).toBe("IDLE");
  });
});

describe("clickAction", () => {
  it("activates from idle, cancels listening/speaking, opens the panel while busy", () => {
    expect(clickAction("IDLE")).toBe("activate");
    expect(clickAction("LISTENING")).toBe("cancel");
    expect(clickAction("SPEAKING")).toBe("cancel");
    for (const v of ["THINKING", "EXECUTING", "AWAITING"] as const) expect(clickAction(v)).toBe("open_panel");
    expect(clickAction("OFFLINE")).toBe("none");
    expect(clickAction("STARTING")).toBe("none");
  });
});

describe("reducer", () => {
  it("applies backend state and clears level and pulse outside LISTENING", () => {
    let m = connected({ interaction: "LISTENING", level: 0.8 });
    m = reducer(m, { type: "backend_state", state: "PROCESSING", substage: "COLLECTING", label: "Reading calendar" });
    expect(m).toMatchObject({ interaction: "PROCESSING", substage: "COLLECTING", level: 0, label: "Reading calendar" });
  });

  it("ignores invalid local triggers instead of forcing a state", () => {
    const m = connected({ interaction: "IDLE" });
    expect(reducer(m, { type: "trigger", trigger: "speech_finished" })).toBe(m);
  });

  it("clamps the audio level to 0..1", () => {
    expect(reducer(connected({}), { type: "level", level: 3 }).level).toBe(1);
    expect(reducer(connected({}), { type: "level", level: -1 }).level).toBe(0);
  });

  it("losing the service zeroes the level and shows OFFLINE", () => {
    const m = reducer(connected({ interaction: "LISTENING", level: 0.5 }), { type: "service", status: "DOWN" });
    expect(m.level).toBe(0);
    expect(deriveVisual(m)).toBe("OFFLINE");
  });

  it("stores and clears a notice", () => {
    const shown = reducer(connected({}), { type: "notice", text: "Sem áudio ainda" });
    expect(shown.notice).toBe("Sem áudio ainda");
    expect(reducer(shown, { type: "notice", text: null }).notice).toBeNull();
  });

  it("merges privacy indicators", () => {
    const m = reducer(connected({}), { type: "privacy", privacy: { microphone: true } });
    expect(m.privacy).toEqual({ microphone: true, camera: false, screen: false, cloud: false });
  });
});
