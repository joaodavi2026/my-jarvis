import type { InteractionState } from "./machine";

export type ServiceStatus = "CONNECTED" | "CONNECTING" | "DOWN";
export type Pulse = "SUCCESS" | "ERROR" | null;
export type Substage = "THINKING" | "COLLECTING" | "ANALYZING" | "COMPOSING";

export type VisualState =
  | "STARTING"
  | "IDLE"
  | "LISTENING"
  | "THINKING"
  | "EXECUTING"
  | "AWAITING"
  | "SPEAKING"
  | "SUCCESS"
  | "ERROR"
  | "OFFLINE";

export interface Privacy {
  microphone: boolean;
  camera: boolean;
  screen: boolean;
  cloud: boolean;
}

export interface AppModel {
  /** "service": driven by the Python service. "simulated": local dev simulator. */
  source: "service" | "simulated";
  service: ServiceStatus;
  interaction: InteractionState;
  substage: Substage;
  pulse: Pulse;
  level: number; // 0..1, microphone level while listening
  muted: boolean;
  badge: boolean; // something relevant is waiting
  privacy: Privacy;
  storageDegraded: boolean;
  label: string; // short operational text from real events (never invented)
}

export const initialModel: AppModel = {
  source: "service",
  service: "CONNECTING",
  interaction: "BOOTING",
  substage: "THINKING",
  pulse: null,
  level: 0,
  muted: false,
  badge: false,
  privacy: { microphone: false, camera: false, screen: false, cloud: false },
  storageDegraded: false,
  label: "",
};

/** The orb shows only what the real state says. Pulses overlay IDLE only. */
export function deriveVisual(m: AppModel): VisualState {
  if (m.source === "service" && m.service !== "CONNECTED") {
    return m.service === "CONNECTING" ? "STARTING" : "OFFLINE";
  }
  switch (m.interaction) {
    case "OFFLINE":
      return "OFFLINE";
    case "BOOTING":
      return "STARTING";
    case "ACTIVATED":
    case "LISTENING":
      return "LISTENING";
    case "PROCESSING":
      return "THINKING";
    case "EXECUTING":
      return "EXECUTING";
    case "AWAITING_CONFIRMATION":
      return "AWAITING";
    case "SPEAKING":
      return "SPEAKING";
    case "ERROR":
      return "ERROR";
    case "CANCELLED":
    case "IDLE":
      return m.pulse ?? "IDLE";
  }
}

export type ClickAction = "activate" | "cancel" | "open_panel" | "none";

/** Orb click semantics: idle starts listening; listening/speaking are interrupted. */
export function clickAction(v: VisualState): ClickAction {
  switch (v) {
    case "IDLE":
    case "SUCCESS":
    case "ERROR":
      return "activate";
    case "LISTENING":
    case "SPEAKING":
      return "cancel";
    case "THINKING":
    case "EXECUTING":
    case "AWAITING":
      return "open_panel";
    case "STARTING":
    case "OFFLINE":
      return "none";
  }
}
