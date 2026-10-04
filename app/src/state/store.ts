import { transition } from "./machine";
import type { InteractionState, Trigger } from "./machine";
import { initialModel } from "./visual";
import type { AppModel, Privacy, Pulse, ServiceStatus, Substage } from "./visual";

export type Action =
  | { type: "service"; status: ServiceStatus }
  | { type: "backend_state"; state: InteractionState; substage?: Substage; label?: string }
  | { type: "trigger"; trigger: Trigger } // local simulator only
  | { type: "level"; level: number }
  | { type: "pulse"; pulse: Pulse }
  | { type: "privacy"; privacy: Partial<Privacy> }
  | { type: "storage"; degraded: boolean }
  | { type: "muted"; muted: boolean }
  | { type: "badge"; badge: boolean }
  | { type: "source"; source: AppModel["source"] };

export function reducer(m: AppModel, a: Action): AppModel {
  switch (a.type) {
    case "service":
      return { ...m, service: a.status, ...(a.status === "DOWN" ? { level: 0 } : {}) };
    case "backend_state":
      return {
        ...m,
        interaction: a.state,
        substage: a.substage ?? "THINKING",
        label: a.label ?? "",
        level: a.state === "LISTENING" ? m.level : 0,
        pulse: null,
      };
    case "trigger": {
      const next = transition(m.interaction, a.trigger);
      if (next === null) return m; // invalid transitions are ignored, never forced
      return { ...m, interaction: next, level: next === "LISTENING" ? m.level : 0, pulse: null };
    }
    case "level":
      return { ...m, level: Math.max(0, Math.min(1, a.level)) };
    case "pulse":
      return { ...m, pulse: a.pulse };
    case "privacy":
      return { ...m, privacy: { ...m.privacy, ...a.privacy } };
    case "storage":
      return { ...m, storageDegraded: a.degraded };
    case "muted":
      return { ...m, muted: a.muted };
    case "badge":
      return { ...m, badge: a.badge };
    case "source":
      return a.source === "simulated"
        ? { ...initialModel, source: "simulated", service: "CONNECTED", interaction: "IDLE" }
        : { ...initialModel, source: "service" };
  }
}
