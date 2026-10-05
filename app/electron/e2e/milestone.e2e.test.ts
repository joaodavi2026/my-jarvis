import { afterEach, describe, expect, it } from "vitest";
import { childPids, isAlive, launchApp, waitUntilDead } from "./harness";
import type { RunningApp } from "./harness";

const apps: RunningApp[] = [];
const start = (env: Record<string, string> = {}) => {
  const app = launchApp(env);
  apps.push(app);
  return app;
};

afterEach(async () => {
  for (const app of apps.splice(0)) {
    if (app.child.exitCode === null) app.child.kill();
    const pid = app.find("service_ready")?.pid;
    if (typeof pid === "number" && isAlive(pid)) process.kill(pid);
  }
});

const MILESTONE = { JARVIS_E2E_SCRIPT: "1" };

describe("JARVIS milestone: Windows -> Electron shell -> orb -> Python -> IPC -> events -> orb -> clean shutdown", () => {
  it("runs the whole chain for real and shuts down cleanly without orphans", async () => {
    const app = start({ ...MILESTONE, JARVIS_E2E_AUTOQUIT: "1" });
    const spawnedPid = (await app.waitFor("service_spawned")).pid as number;
    const tree = [spawnedPid, ...childPids(spawnedPid)]; // launcher + real interpreter
    expect(tree.length, "venv launcher + real interpreter").toBeGreaterThanOrEqual(2);
    const code = await Promise.race([app.exited, new Promise<null>((r) => setTimeout(() => r(null), 100_000))]);
    const trace = app.trace();
    const names = trace.map((l) => l.ev);

    // 1. shell + orb
    const shown = app.find("orb_shown")!;
    expect(shown, "orb window shown").toBeTruthy();
    expect(shown.alwaysOnTop).toBe(true);
    expect(shown.bounds).toMatchObject({ width: 160, height: 160 });

    // 2. Rust-less supervisor starts Python and gets the ready line (token travels only through stdin)
    const spawned = app.find("service_spawned")!;
    const ready = app.find("service_ready")!;
    expect(typeof spawned.pid).toBe("number");
    expect(ready.pid).toBe(spawned.pid);
    expect(ready.port as number).toBeGreaterThan(0);

    // 3. authenticated IPC + health check
    expect(names.indexOf("ipc_connected")).toBeGreaterThan(names.indexOf("service_ready"));
    const health = app.find("health_ok")!;
    expect(health.state).toBe("IDLE");

    // 4. Python event -> shell -> orb: ERROR then back to IDLE, all driven by the real state machine
    const changed = trace.filter((l) => l.ev === "event_from_service" && l.type === "state.changed").map((l) => l.state);
    expect(changed).toContain("ERROR");
    expect(changed).toContain("IDLE");
    const visuals = trace.filter((l) => l.ev === "visual").map((l) => l.state);
    expect(visuals).toContain("ERROR");
    expect(visuals.lastIndexOf("IDLE")).toBeGreaterThan(visuals.indexOf("ERROR"));
    expect(names).toContain("script_done");
    expect(names).not.toContain("script_failed");

    // 5. clean shutdown: Python exits with code 0 and the process is gone
    expect(names.indexOf("quit_started")).toBeGreaterThan(names.indexOf("script_done"));
    const pyExit = app.find("python_exited")!;
    expect(pyExit.code).toBe(0);
    expect(code).toBe(0);
    expect(isAlive(spawned.pid as number)).toBe(false);
    for (const pid of tree) expect(isAlive(pid), "process " + pid + " should be gone").toBe(false);

    // 6. the session token never reaches the trace (64 hex chars would be a token)
    expect(JSON.stringify(trace)).not.toMatch(/[0-9a-f]{64}/);
  });

  it("never leaves an orphan Python process when the shell is killed abruptly", async () => {
    const app = start(MILESTONE);
    await app.waitFor("script_done");
    const pid = app.find("service_spawned")!.pid as number;
    const tree = [pid, ...childPids(pid)];
    expect(isAlive(pid)).toBe(true);
    app.child.kill(); // hard kill of the Electron main process: no chance to run any shutdown code
    for (const id of tree) expect(await waitUntilDead(id, 15_000), "process " + id + " should be gone").toBe(true);
  });

  it("shows OFFLINE honestly when the Python service cannot be started", async () => {
    const app = start({ JARVIS_PYTHON: "Z:/does/not/exist/python.exe", JARVIS_E2E_AUTOQUIT: "1" });
    const code = await Promise.race([app.exited, new Promise<null>((r) => setTimeout(() => r(null), 60_000))]);
    const trace = app.trace();
    expect(trace.some((l) => l.ev === "service_launch_missing")).toBe(true);
    expect(trace.filter((l) => l.ev === "visual").map((l) => l.state)).toContain("OFFLINE");
    expect(trace.some((l) => l.ev === "visual" && l.state === "LISTENING")).toBe(false);
    expect(code).toBe(0);
  });

  it("a real click on the orb reaches the service and gives visible feedback (no pretending to listen)", async () => {
    const app = start({ JARVIS_E2E_CLICK: "1", JARVIS_E2E_AUTOQUIT: "1" });
    const code = await Promise.race([app.exited, new Promise<null>((r) => setTimeout(() => r(null), 100_000))]);
    const trace = app.trace();
    expect(trace.find((l) => l.ev === "test_click")?.visual).toBe("IDLE");
    const fromService = trace.filter((l) => l.ev === "event_from_service").map((l) => l.type);
    expect(fromService).toContain("error.occurred");
    expect(fromService).toContain("feedback.pulse");
    const visuals = trace.filter((l) => l.ev === "visual").map((l) => l.state);
    expect(visuals.slice(visuals.indexOf("IDLE"))).toEqual(["IDLE", "ERROR", "IDLE"]);
    expect(visuals).not.toContain("LISTENING"); // there is no microphone yet
    expect(code).toBe(0);
  });
});
