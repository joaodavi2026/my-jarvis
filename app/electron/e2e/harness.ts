// Launches the real Electron app (stock electron.exe) with the real Python service and reads its trace.
import { execFileSync, spawn } from "node:child_process";
import type { ChildProcess } from "node:child_process";
import * as fs from "node:fs";
import { createRequire } from "node:module";
import * as os from "node:os";
import * as path from "node:path";

const require = createRequire(import.meta.url);
export const electronExe = require("electron") as string;
export const appDir = path.resolve(__dirname, "..", "..");

export interface TraceLine {
  ts: number;
  ev: string;
  [key: string]: unknown;
}

export interface RunningApp {
  child: ChildProcess;
  tmp: string;
  trace(): TraceLine[];
  find(ev: string, pred?: (l: TraceLine) => boolean): TraceLine | undefined;
  waitFor(ev: string, timeoutMs?: number, pred?: (l: TraceLine) => boolean): Promise<TraceLine>;
  exited: Promise<number | null>;
}

export function launchApp(extraEnv: Record<string, string> = {}): RunningApp {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), "jarvis-e2e-"));
  const out = path.join(tmp, "trace.jsonl");
  const env: NodeJS.ProcessEnv = {
    ...process.env,
    JARVIS_E2E_OUT: out,
    JARVIS_USER_DATA: path.join(tmp, "userdata"),
    JARVIS_INTERNAL_ROOT: path.join(tmp, "internal"),
    JARVIS_DEV_TOOLS: "1",
    ...extraEnv,
  };
  delete env.ELECTRON_RUN_AS_NODE;
  const child = spawn(electronExe, [appDir], { env, stdio: "ignore", windowsHide: false });
  const exited = new Promise<number | null>((resolve) => child.on("exit", (code) => resolve(code)));
  const trace = (): TraceLine[] => {
    try {
      return fs.readFileSync(out, "utf8").split("\n").filter(Boolean).map((l) => JSON.parse(l) as TraceLine);
    } catch {
      return [];
    }
  };
  const find = (ev: string, pred: (l: TraceLine) => boolean = () => true) => trace().find((l) => l.ev === ev && pred(l));
  const waitFor = async (ev: string, timeoutMs = 60_000, pred: (l: TraceLine) => boolean = () => true) => {
    const deadline = Date.now() + timeoutMs;
    for (;;) {
      const hit = find(ev, pred);
      if (hit) return hit;
      if (Date.now() > deadline) throw new Error("timed out waiting for " + ev + "; trace: " + trace().map((l) => l.ev).join(","));
      await new Promise((r) => setTimeout(r, 100));
    }
  };
  return { child, tmp, trace, find, waitFor, exited };
}

export function isAlive(pid: number): boolean {
  try {
    process.kill(pid, 0);
    return true;
  } catch {
    return false;
  }
}

export async function waitUntilDead(pid: number, timeoutMs: number): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (!isAlive(pid)) return true;
    await new Promise((r) => setTimeout(r, 100));
  }
  return !isAlive(pid);
}

/** PIDs of the direct children of `pid` (the venv launcher spawns the real interpreter). */
export function childPids(pid: number): number[] {
  try {
    const out = execFileSync(
      "powershell",
      ["-NoProfile", "-Command", "(Get-CimInstance Win32_Process -Filter 'ParentProcessId=" + pid + "').ProcessId"],
      { encoding: "utf8", windowsHide: true },
    );
    return out.split(String.fromCharCode(10)).map((l) => Number(l.trim())).filter((n) => Number.isInteger(n) && n > 0);
  } catch {
    return [];
  }
}
