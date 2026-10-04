import type { Action } from "../state/store";
import type { InteractionState } from "../state/machine";
import { ALL_STATES } from "../state/machine";
import type { Substage } from "../state/visual";
import type { BackendEvent } from "./bridge";

const SUBSTAGES: Substage[] = ["THINKING", "COLLECTING", "ANALYZING", "COMPOSING"];

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === "object" && v !== null;

/** Pure mapping from a backend event (see contracts/event-catalog.md) to a reducer action. */
export function toAction(e: BackendEvent): Action | null {
  const p = e.payload ?? {};
  switch (e.type) {
    case "state.changed": {
      const state = p.state;
      if (typeof state !== "string" || !ALL_STATES.includes(state as InteractionState)) return null;
      const substage = SUBSTAGES.find((s) => s === p.substage);
      return {
        type: "backend_state",
        state: state as InteractionState,
        substage,
        label: typeof p.label === "string" ? p.label : undefined,
      };
    }
    case "audio.level":
      return typeof p.level === "number" && Number.isFinite(p.level) ? { type: "level", level: p.level } : null;
    case "privacy.changed":
      return isObject(p) ? { type: "privacy", privacy: pickPrivacy(p) } : null;
    case "storage.status_changed":
      return { type: "storage", degraded: p.mode === "DEGRADED" || p.mode === "STORAGE_DEGRADED" };
    case "feedback.pulse":
      return p.kind === "SUCCESS" || p.kind === "ERROR" ? { type: "pulse", pulse: p.kind } : null;
    case "service.status":
      return p.status === "CONNECTED" || p.status === "CONNECTING" || p.status === "DOWN"
        ? { type: "service", status: p.status }
        : null;
    default:
      return null;
  }
}

function pickPrivacy(p: Record<string, unknown>) {
  const out: Partial<Record<"microphone" | "camera" | "screen" | "cloud", boolean>> = {};
  for (const key of ["microphone", "camera", "screen", "cloud"] as const) {
    if (typeof p[key] === "boolean") out[key] = p[key] as boolean;
  }
  return out;
}
