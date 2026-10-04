// JARVIS desktop shell (Electron main process): lifecycle, tray, orb/panel windows, service supervisor and
// the authenticated IPC link. No assistant logic lives here (see docs/ARCHITECTURE.md section 3).
import { app, BrowserWindow, ipcMain, Menu, nativeImage, Tray } from "electron";
import type { IpcMainEvent, IpcMainInvokeEvent } from "electron";
import * as fs from "node:fs";
import * as path from "node:path";
import { IpcClient } from "./ipcClient";
import { resolveServiceLaunch } from "./launch";
import { orbMenuTemplate, trayMenuTemplate } from "./menus";
import { isCorner } from "./placement";
import { loadPrefs, savePrefs } from "./prefs";
import type { Prefs } from "./prefs";
import { snapshotAllStates } from "./devtools";
import { ServiceSupervisor } from "./supervisor";
import type { ReadyInfo } from "./supervisor";
import { assetPath, createOrbWindow, createPanelWindow, OrbDragger, placeOrb } from "./windows";

type ServiceStatus = "CONNECTING" | "CONNECTED" | "DOWN";
const SEND_ALLOWED = new Set(["activation.orb_clicked", "activation.hotkey_pressed", "activation.cancelled", "confirmation.answered"]);

if (process.env.JARVIS_USER_DATA) app.setPath("userData", process.env.JARVIS_USER_DATA);

// Milestone/e2e trace: one JSON line per step. Never contains the token.
const E2E_OUT = process.env.JARVIS_E2E_OUT;
function trace(ev: string, data: Record<string, unknown> = {}): void {
  if (E2E_OUT) fs.appendFileSync(E2E_OUT, JSON.stringify({ ts: Date.now(), ev, ...data }) + "\n");
}

let orb: BrowserWindow | null = null;
let panel: BrowserWindow | null = null;
let tray: Tray | null = null;
let dragger: OrbDragger | null = null;
let prefs: Prefs;
let prefsFile = "";
let serviceStatus: ServiceStatus = "CONNECTING";
let lastState: Record<string, unknown> | null = null;
let lastStorage: Record<string, unknown> | null = null;
let muted = false;
let quitting = false;
let ipc: IpcClient | null = null;
let supervisor: ServiceSupervisor | null = null;
let connectFailures = 0;
let lastVisual = "";
const visualWaiters: { state: string; resolve: () => void }[] = [];

const windows = () => [orb, panel].filter((w): w is BrowserWindow => !!w && !w.isDestroyed());
const isOurs = (e: IpcMainEvent | IpcMainInvokeEvent) => windows().some((w) => w.webContents.id === e.sender.id);

function broadcast(channel: string, payload: unknown, except?: number): void {
  for (const w of windows()) if (w.webContents.id !== except) w.webContents.send(channel, payload);
}

function emitBackend(type: string, payload: Record<string, unknown>): void {
  broadcast("jarvis:event", { type, payload });
}

function setStatus(status: ServiceStatus): void {
  serviceStatus = status;
  emitBackend("service.status", { status });
  trace("service_status", { status });
}

function syncWindow(win: BrowserWindow): void {
  win.webContents.send("jarvis:event", { type: "service.status", payload: { status: serviceStatus } });
  if (serviceStatus === "CONNECTED") {
    if (lastStorage) win.webContents.send("jarvis:event", { type: "storage.status_changed", payload: lastStorage });
    if (lastState) win.webContents.send("jarvis:event", { type: "state.changed", payload: lastState });
  }
}

function showPanel(): void {
  if (!panel || panel.isDestroyed()) return;
  panel.show();
  panel.focus();
}

function savePrefsSafe(): void {
  try {
    savePrefs(prefsFile, prefs);
  } catch {
    /* preferences are best effort */
  }
}

function setCorner(id: string): void {
  const corner = id.replace("corner:", "");
  if (!isCorner(corner) || !orb) return;
  prefs = { orbCorner: corner, orbPosition: null };
  savePrefsSafe();
  placeOrb(orb, prefs.orbCorner, null);
}

function onMenuAction(id: string): void {
  if (id.startsWith("corner:")) return setCorner(id);
  switch (id) {
    case "quit":
      return void shutdown("menu");
    case "open_panel":
    case "settings":
    case "history":
    case "microphone":
    case "camera":
    case "privacy":
      return showPanel();
    case "restart_service":
      return void restartService();
    case "mute":
      muted = !muted;
      return orb?.webContents.send("jarvis:menu", id);
    default:
      return orb?.webContents.send("jarvis:menu", id);
  }
}

async function restartService(): Promise<void> {
  ipc?.close();
  setStatus("CONNECTING");
  await supervisor?.restart();
}

async function shutdown(reason: string): Promise<void> {
  if (quitting) return;
  quitting = true;
  trace("quit_started", { reason });
  ipc?.close();
  await supervisor?.stop();
  trace("service_stopped");
  app.exit(0);
}

// ── service link ────────────────────────────────────────────────
async function connectToService(info: ReadyInfo): Promise<void> {
  ipc?.close();
  const client = new IpcClient();
  ipc = client;
  try {
    await client.connect(info.port, info.token);
  } catch (err) {
    trace("ipc_connect_failed", { code: (err as { code?: string }).code, message: (err as Error).message });
    setStatus("DOWN");
    if (++connectFailures <= 3 && !quitting) void supervisor?.restart();
    return;
  }
  connectFailures = 0;
  trace("ipc_connected", { pid: info.pid });
  client.on("event", (message: { type: string; payload: Record<string, unknown> }) => {
    trace("event_from_service", { type: message.type, state: message.payload.state });
    if (message.type === "state.changed") lastState = message.payload;
    if (message.type === "storage.status_changed") lastStorage = message.payload;
    emitBackend(message.type, message.payload);
  });
  client.on("close", () => {
    if (quitting || ipc !== client) return;
    trace("ipc_closed");
    setStatus("DOWN");
    void supervisor?.restart();
  });
  try {
    const health = await client.request("health.get");
    const caps = health.capabilities as Record<string, { status?: string }>;
    trace("health_ok", { state: health.state, storage: caps.storage?.status, pid: info.pid });
    lastState = { state: health.state as string };
    lastStorage = (await client.request("storage.get")) as Record<string, unknown>;
  } catch (err) {
    trace("health_failed", { code: (err as { code?: string }).code });
  }
  setStatus("CONNECTED");
  if (lastStorage) emitBackend("storage.status_changed", lastStorage);
  if (lastState) emitBackend("state.changed", lastState);
  if (process.env.JARVIS_E2E_SCRIPT === "1") void runE2eScript(client);
}

function waitForVisual(state: string, timeoutMs: number): Promise<void> {
  if (lastVisual === state) return Promise.resolve();
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error("visual " + state + " not reached")), timeoutMs);
    visualWaiters.push({
      state,
      resolve: () => {
        clearTimeout(timer);
        resolve();
      },
    });
  });
}

// Real chain for the milestone: Python state machine -> EventBus -> IPC -> main -> renderer -> orb.
async function runE2eScript(client: IpcClient): Promise<void> {
  try {
    await client.request("dev.dispatch_trigger", { trigger: "failure" });
    trace("script_trigger", { trigger: "failure" });
    await waitForVisual("ERROR", 10_000);
    await client.request("dev.dispatch_trigger", { trigger: "error_acknowledged" });
    trace("script_trigger", { trigger: "error_acknowledged" });
    await waitForVisual("IDLE", 10_000);
    trace("script_done");
  } catch (err) {
    trace("script_failed", { error: (err as Error).message });
  }
  if (process.env.JARVIS_E2E_AUTOQUIT === "1") void shutdown("e2e");
}

// ── app wiring ──────────────────────────────────────────────────
function registerIpc(): void {
  ipcMain.handle("jarvis:send", async (e, type: unknown, payload: unknown) => {
    if (!isOurs(e) || typeof type !== "string") return { ok: false, error: "rejected" };
    if (!SEND_ALLOWED.has(type) && !type.startsWith("shell.")) return { ok: false, error: "not_allowed" };
    try {
      if (!ipc?.connected) return { ok: false, error: "service_unavailable" };
      ipc.sendEvent(type, (payload && typeof payload === "object" ? payload : {}) as Record<string, unknown>);
      return { ok: true };
    } catch {
      return { ok: false, error: "service_unavailable" };
    }
  });
  ipcMain.on("jarvis:broadcast-action", (e, action: unknown) => {
    if (isOurs(e)) broadcast("jarvis:action", action, e.sender.id);
  });
  ipcMain.on("jarvis:sync", (e) => {
    const win = BrowserWindow.fromWebContents(e.sender);
    if (win && isOurs(e)) syncWindow(win);
  });
  ipcMain.on("orb:drag-start", (e, sx: number, sy: number) => isOurs(e) && dragger?.begin(sx, sy));
  ipcMain.on("orb:drag-move", (e, sx: number, sy: number) => isOurs(e) && dragger?.move(sx, sy));
  ipcMain.on("orb:drag-end", (e) => {
    if (!isOurs(e)) return;
    const pos = dragger?.end();
    if (pos) {
      prefs = { ...prefs, orbPosition: pos };
      savePrefsSafe();
    }
  });
  ipcMain.on("orb:menu", (e) => {
    if (isOurs(e) && orb) Menu.buildFromTemplate(orbMenuTemplate(onMenuAction, muted)).popup({ window: orb });
  });
  ipcMain.on("panel:open", (e) => isOurs(e) && showPanel());
  ipcMain.on("e2e:visual", (e, state: unknown) => {
    if (!isOurs(e) || typeof state !== "string" || BrowserWindow.fromWebContents(e.sender) !== orb) return;
    lastVisual = state;
    trace("visual", { state });
    for (let i = visualWaiters.length - 1; i >= 0; i--) {
      if (visualWaiters[i].state === state) visualWaiters.splice(i, 1)[0].resolve();
    }
  });
}

function startService(): void {
  const launch = resolveServiceLaunch(process.env, path.resolve(__dirname, "..", ".."));
  if (!launch) {
    trace("service_launch_missing");
    setStatus("DOWN");
    if (process.env.JARVIS_E2E_AUTOQUIT === "1") setTimeout(() => void shutdown("e2e"), 3000);
    return;
  }
  supervisor = new ServiceSupervisor({ launch });
  supervisor.on("ready", (info: ReadyInfo) => {
    trace("service_ready", { port: info.port, pid: info.pid });
    void connectToService(info);
  });
  supervisor.on("down", (d: { reason: string; willRestart: boolean }) => {
    trace("service_down", { reason: d.reason, willRestart: d.willRestart });
    ipc?.close();
    setStatus("DOWN");
  });
  supervisor.on("state", (s: string) => {
    if (s === "STARTING") setStatus("CONNECTING");
  });
  supervisor.on("exited", (e: { code: number | null; pid?: number }) => trace("python_exited", { code: e.code, pid: e.pid }));
  supervisor.on("log", (line: string) => trace("service_log", { line: line.slice(0, 300) }));
  supervisor.start();
  trace("service_spawned", { pid: supervisor.pid });
}

if (!app.requestSingleInstanceLock()) {
  app.exit(0);
} else {
  app.on("second-instance", () => orb && placeOrb(orb, prefs.orbCorner, prefs.orbPosition));
  app.on("window-all-closed", () => {}); // JARVIS keeps running in the background
  app.on("before-quit", (event) => {
    if (!quitting) {
      event.preventDefault();
      void shutdown("before-quit");
    }
  });

  void app.whenReady().then(() => {
    app.setAppUserModelId("app.jarvis.desktop");
    prefsFile = path.join(app.getPath("userData"), "shell-prefs.json");
    prefs = loadPrefs(prefsFile);
    registerIpc();

    orb = createOrbWindow();
    panel = createPanelWindow();
    dragger = new OrbDragger(orb);
    panel.on("close", (event) => {
      if (!quitting) {
        event.preventDefault();
        panel?.hide();
      }
    });
    orb.webContents.on("did-finish-load", () => {
      if (!orb) return;
      placeOrb(orb, prefs.orbCorner, prefs.orbPosition);
      trace("orb_shown", { bounds: orb.getBounds(), alwaysOnTop: orb.isAlwaysOnTop() });
      syncWindow(orb);
      const snapshotDir = process.env.JARVIS_E2E_SNAPSHOT_DIR;
      if (snapshotDir) {
        void snapshotAllStates(orb, snapshotDir).then((files) => {
          trace("snapshots_saved", { count: files.length });
          if (process.env.JARVIS_E2E_AUTOQUIT === "1") void shutdown("snapshots");
        });
      }
    });
    panel.webContents.on("did-finish-load", () => panel && syncWindow(panel));

    tray = new Tray(nativeImage.createFromPath(assetPath("tray.png")));
    tray.setToolTip("JARVIS");
    tray.setContextMenu(Menu.buildFromTemplate(trayMenuTemplate(onMenuAction)));
    tray.on("click", showPanel);

    startService();
  });
}
