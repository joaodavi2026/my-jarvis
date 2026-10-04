import { useEffect, useReducer, useRef } from "react";
import { bridge } from "../ipc/bridge";
import { toAction } from "../ipc/events";
import { playFlow } from "./sim";
import type { FlowName } from "./sim";
import { reducer } from "./store";
import type { Action } from "./store";
import { initialModel } from "./visual";
import type { AppModel } from "./visual";

/** Shared by the orb and panel windows: backend events + broadcast actions feed one reducer. */
export function useAppModel(): [AppModel, (a: Action) => void] {
  const [model, dispatch] = useReducer(reducer, initialModel);
  const modelRef = useRef(model);
  modelRef.current = model;

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    if (params.get("sim") === "1") dispatch({ type: "source", source: "simulated" });

    const cleanups: Array<() => void> = [];
    cleanups.push(
      bridge.onBackendEvent((e) => {
        if (modelRef.current.source !== "service") return;
        const action = toAction(e);
        if (action) dispatch(action);
      }),
    );
    let stopFlow: (() => void) | null = null;
    const FLOW_PREFIX = "__flow:";
    cleanups.push(
      bridge.onAction((a) => {
        // The panel asks every window to play a simulator flow locally (dev only).
        if (a.type === "trigger" && a.trigger.startsWith(FLOW_PREFIX)) {
          stopFlow?.();
          stopFlow = playFlow(a.trigger.slice(FLOW_PREFIX.length) as FlowName, dispatch);
          return;
        }
        dispatch(a);
      }),
    );
    bridge.requestSync(); // replay the current service status/state to this window
    return () => cleanups.forEach((off) => off());
  }, []);

  // SUCCESS / ERROR pulses are transient: clear them so the orb returns to IDLE.
  useEffect(() => {
    if (!model.pulse) return;
    const id = setTimeout(() => dispatch({ type: "pulse", pulse: null }), 1300);
    return () => clearTimeout(id);
  }, [model.pulse]);

  return [model, dispatch];
}
