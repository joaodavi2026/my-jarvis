// Dev simulator: drives the real reducer through scripted flows so visuals can be reviewed
// before the Python service exists. It never runs in service mode.
import type { Action } from "./store";

export type FlowName = "voice" | "tool" | "confirm" | "briefing" | "error";
type Step = [delayMs: number, action: Action];

const t = (trigger: string): Action => ({ type: "trigger", trigger });

export const FLOWS: Record<FlowName, Step[]> = {
  voice: [
    [0, t("activation_requested")],
    [300, t("listening_started")],
    [3200, t("transcription_ready")],
    [1200, t("response_ready")],
    [3000, t("speech_finished")],
    [0, { type: "pulse", pulse: "SUCCESS" }],
    [1200, { type: "pulse", pulse: null }],
  ],
  tool: [
    [0, t("activation_requested")],
    [200, t("listening_started")],
    [1800, t("transcription_ready")],
    [700, t("tool_started")],
    [1800, t("tool_completed")],
    [300, t("response_ready")],
    [1800, t("speech_finished")],
    [0, { type: "pulse", pulse: "SUCCESS" }],
    [1200, { type: "pulse", pulse: null }],
  ],
  confirm: [
    [0, t("activation_requested")],
    [200, t("listening_started")],
    [1500, t("transcription_ready")],
    [800, t("confirmation_requested")],
    [3000, t("confirmation_answered")],
    [600, t("response_ready")],
    [1500, t("speech_finished")],
  ],
  briefing: [
    [0, t("activation_requested")],
    [200, t("listening_started")],
    [1200, t("transcription_ready")],
    [0, { type: "backend_state", state: "PROCESSING", substage: "COLLECTING", label: "Coletando" }],
    [1500, { type: "backend_state", state: "PROCESSING", substage: "ANALYZING", label: "Analisando" }],
    [1500, { type: "backend_state", state: "PROCESSING", substage: "COMPOSING", label: "Compondo" }],
    [1500, t("response_ready")],
    [3000, t("speech_finished")],
  ],
  error: [
    [0, t("activation_requested")],
    [200, t("listening_started")],
    [1000, t("failure")],
    [2500, t("error_acknowledged")],
  ],
};

/** Plays a flow; returns a cancel function. While LISTENING it feeds a smooth fake mic level. */
export function playFlow(
  name: FlowName,
  dispatch: (a: Action) => void,
  timers: { set: typeof setTimeout; clear: typeof clearTimeout } = { set: setTimeout, clear: clearTimeout },
): () => void {
  const handles: ReturnType<typeof setTimeout>[] = [];
  let at = 0;
  for (const [delay, action] of FLOWS[name]) {
    at += delay;
    handles.push(timers.set(() => dispatch(action), at));
  }
  const meter = setInterval(() => {
    const phase = performance.now() / 1000;
    dispatch({ type: "level", level: 0.35 + 0.3 * Math.sin(phase * 5) * Math.sin(phase * 1.7) + 0.2 * Math.random() });
  }, 60);
  handles.push(timers.set(() => clearInterval(meter), at + 50));
  return () => {
    clearInterval(meter);
    handles.forEach((h) => timers.clear(h));
  };
}
