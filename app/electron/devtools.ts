// Test-only helper (enabled by JARVIS_E2E_SNAPSHOT_DIR): renders the real orb in every visual state and saves PNGs,
// so the look can be reviewed even when the desktop cannot be screen-captured. Never active in normal use.
import type { BrowserWindow } from "electron";
import * as fs from "node:fs";
import * as path from "node:path";

type Action = Record<string, unknown>;
const trigger = (t: string): Action => ({ type: "trigger", trigger: t });

const STEPS: { name: string; actions: Action[] }[] = [
  { name: "IDLE", actions: [{ type: "source", source: "simulated" }] },
  { name: "LISTENING", actions: [trigger("activation_requested"), trigger("listening_started"), { type: "level", level: 0.7 }] },
  { name: "THINKING", actions: [trigger("transcription_ready")] },
  { name: "EXECUTING", actions: [trigger("tool_started")] },
  { name: "AWAITING", actions: [trigger("confirmation_requested")] },
  { name: "SPEAKING", actions: [trigger("confirmation_answered"), trigger("response_ready")] },
  { name: "SUCCESS", actions: [trigger("speech_finished"), { type: "pulse", pulse: "SUCCESS" }] },
  { name: "ERROR", actions: [{ type: "pulse", pulse: null }, trigger("failure")] },
  { name: "OFFLINE", actions: [trigger("service_lost")] },
];

const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

export async function snapshotAllStates(orb: BrowserWindow, dir: string): Promise<string[]> {
  fs.mkdirSync(dir, { recursive: true });
  await orb.webContents.executeJavaScript("document.body.style.background = '#0b1220'");
  const saved: string[] = [];
  for (const step of STEPS) {
    for (const action of step.actions) orb.webContents.send("jarvis:action", action);
    await wait(900); // let the CSS animation settle
    const image = await orb.webContents.capturePage();
    const file = path.join(dir, "orb-" + step.name + ".png");
    fs.writeFileSync(file, image.toPNG());
    saved.push(file);
  }
  return saved;
}
