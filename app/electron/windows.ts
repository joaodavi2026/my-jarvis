// Orb and panel windows. Both are locked down: sandbox, context isolation, no Node, no navigation, no popups.
import { BrowserWindow, screen } from "electron";
import * as path from "node:path";
import { cornerPosition, visiblePosition } from "./placement";
import type { Corner } from "./placement";

export const ORB_WINDOW = { width: 160, height: 160 };
const ORB_CORE = 64;
const MARGIN = 12;

const appRoot = path.join(__dirname, "..");
export const assetPath = (name: string) => path.join(appRoot, "electron", "assets", name);

function secureOptions(): Electron.WebPreferences {
  return {
    preload: path.join(__dirname, "preload.js"),
    contextIsolation: true,
    nodeIntegration: false,
    sandbox: true,
    webSecurity: true,
    backgroundThrottling: false,
  };
}

function lockDown(win: BrowserWindow): void {
  win.webContents.setWindowOpenHandler(() => ({ action: "deny" }));
  win.webContents.on("will-navigate", (event) => event.preventDefault());
}

function load(win: BrowserWindow, page: string): Promise<void> {
  const devUrl = process.env.JARVIS_DEV_URL;
  if (devUrl) return win.loadURL(devUrl.replace(/\/$/, "") + "/" + page);
  return win.loadFile(path.join(appRoot, "dist", page));
}

export function createOrbWindow(): BrowserWindow {
  const win = new BrowserWindow({
    ...ORB_WINDOW,
    transparent: true,
    frame: false,
    alwaysOnTop: true,
    resizable: false,
    maximizable: false,
    minimizable: false,
    fullscreenable: false,
    hasShadow: false,
    skipTaskbar: true,
    show: false,
    title: "JARVIS Orb",
    icon: assetPath("icon.png"),
    webPreferences: secureOptions(),
  });
  win.setAlwaysOnTop(true, "screen-saver");
  lockDown(win);
  void load(win, "index.html");
  return win;
}

export function createPanelWindow(): BrowserWindow {
  const win = new BrowserWindow({
    width: 400,
    height: 560,
    transparent: true,
    frame: false,
    resizable: false,
    hasShadow: false,
    show: false,
    title: "JARVIS",
    icon: assetPath("icon.png"),
    webPreferences: secureOptions(),
  });
  lockDown(win);
  void load(win, "panel.html");
  return win;
}

/** Places the orb at its saved position (if still on a display) or at the configured corner, then shows it. */
export function placeOrb(win: BrowserWindow, corner: Corner, saved: { x: number; y: number } | null): void {
  const areas = screen.getAllDisplays().map((d) => d.workArea);
  const size = win.getBounds();
  const restored = saved ? visiblePosition(areas, saved, size) : null;
  const position = restored ?? cornerPosition(screen.getPrimaryDisplay().workArea, size, ORB_CORE, corner, MARGIN);
  win.setPosition(Math.round(position.x), Math.round(position.y));
  win.showInactive();
}

/** Manual drag: the renderer sends screen coordinates, the main process moves the window. */
export class OrbDragger {
  private start: { sx: number; sy: number; wx: number; wy: number } | null = null;
  constructor(private readonly win: BrowserWindow) {}

  begin(sx: number, sy: number): void {
    const [wx, wy] = this.win.getPosition();
    this.start = { sx, sy, wx, wy };
  }

  move(sx: number, sy: number): void {
    if (!this.start) return;
    this.win.setPosition(Math.round(this.start.wx + sx - this.start.sx), Math.round(this.start.wy + sy - this.start.sy));
  }

  end(): { x: number; y: number } | null {
    if (!this.start) return null;
    this.start = null;
    const [x, y] = this.win.getPosition();
    return { x, y };
  }
}
