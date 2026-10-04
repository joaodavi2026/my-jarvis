// Interaction state machine. The transition table is NOT duplicated here: it is read
// from contracts/state-machine.json, the same file the Python service will load.
import spec from "../../../contracts/state-machine.json";

export type InteractionState =
  | "BOOTING"
  | "IDLE"
  | "ACTIVATED"
  | "LISTENING"
  | "PROCESSING"
  | "EXECUTING"
  | "AWAITING_CONFIRMATION"
  | "SPEAKING"
  | "CANCELLED"
  | "ERROR"
  | "OFFLINE";

export type Trigger = string;

interface Transition {
  from: string;
  on: string;
  to: string;
}

const table = new Map<string, InteractionState>();
for (const t of spec.transitions as Transition[]) {
  table.set(`${t.from}|${t.on}`, t.to as InteractionState);
}
const cancellable = new Set<string>(spec.cancellable_from);

export const INITIAL_STATE = spec.initial as InteractionState;
export const ALL_STATES = spec.states as InteractionState[];
export const TRANSIENT_STATES = new Set<string>(spec.transient);

/** Returns the next state, or null when the trigger is not valid from `state`. */
export function transition(state: InteractionState, trigger: Trigger): InteractionState | null {
  switch (trigger) {
    case "cancel_requested":
      return cancellable.has(state) ? "CANCELLED" : null;
    case "failure":
      return state === "BOOTING" ? null : "ERROR";
    case "service_lost":
      return "OFFLINE";
    default:
      return table.get(`${state}|${trigger}`) ?? null;
  }
}
