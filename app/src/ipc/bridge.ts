// The webview talks only to the Electron main process through the preload API (window.jarvis).
// It never sees the service port or the session token.
import type { Action } from "../state/store";

export interface BackendEvent {
  type: string;
  payload?: Record<string, unknown>;
}

export type Unlisten = () => void;

export interface Bridge {
  readonly kind: "electron" | "browser";
  /** Events forwarded by the shell from the Python service (allow-listed UI events). */
  onBackendEvent(cb: (e: BackendEvent) => void): Unlisten;
  /** Reducer actions broadcast between the app windows (dev simulator only). */
  onAction(cb: (a: Action) => void): Unlisten;
  broadcastAction(a: Action): void;
  /** Choices made in the native orb context menu / tray. */
  onMenu(cb: (action: string) => void): Unlisten;
  send(type: string, payload?: Record<string, unknown>): Promise<void>;
  dragStart(screenX: number, screenY: number): void;
  dragMove(screenX: number, screenY: number): void;
  dragEnd(): void;
  showOrbMenu(): void;
  openPanel(): void;
  /** Ask the shell to replay the current service status and state (call after subscribing). */
  requestSync(): void;
  /** Reports the visual state actually rendered (used by the end-to-end milestone test). */
  reportVisual(state: string): void;
}

interface ElectronApi {
  onBackendEvent(cb: (e: BackendEvent) => void): Unlisten;
  onAction(cb: (a: Action) => void): Unlisten;
  onMenu(cb: (action: string) => void): Unlisten;
  broadcastAction(a: Action): void;
  send(type: string, payload?: Record<string, unknown>): Promise<unknown>;
  dragStart(x: number, y: number): void;
  dragMove(x: number, y: number): void;
  dragEnd(): void;
  showOrbMenu(): void;
  openPanel(): void;
  reportVisual(state: string): void;
  requestSync(): void;
}

const api = (globalThis as unknown as { jarvis?: ElectronApi }).jarvis;
const noop = () => {};

class ElectronBridge implements Bridge {
  readonly kind = "electron" as const;
  constructor(private readonly a: ElectronApi) {}
  onBackendEvent = (cb: (e: BackendEvent) => void) => this.a.onBackendEvent(cb);
  onAction = (cb: (a: Action) => void) => this.a.onAction(cb);
  onMenu = (cb: (action: string) => void) => this.a.onMenu(cb);
  broadcastAction = (a: Action) => this.a.broadcastAction(a);
  async send(type: string, payload?: Record<string, unknown>) {
    await this.a.send(type, payload);
  }
  dragStart = (x: number, y: number) => this.a.dragStart(x, y);
  dragMove = (x: number, y: number) => this.a.dragMove(x, y);
  dragEnd = () => this.a.dragEnd();
  showOrbMenu = () => this.a.showOrbMenu();
  openPanel = () => this.a.openPanel();
  requestSync = () => this.a.requestSync();
  reportVisual = (state: string) => this.a.reportVisual(state);
}

/** Plain browser (npm run dev, tests): only the dev simulator works, through a BroadcastChannel. */
class BrowserBridge implements Bridge {
  readonly kind = "browser" as const;
  private channel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel("jarvis-dev") : null;
  onBackendEvent = () => noop;
  onAction(cb: (a: Action) => void): Unlisten {
    const handler = (ev: MessageEvent) => cb(ev.data as Action);
    this.channel?.addEventListener("message", handler);
    return () => this.channel?.removeEventListener("message", handler);
  }
  broadcastAction(a: Action) {
    this.channel?.postMessage(a);
  }
  onMenu = () => noop;
  async send() {}
  dragStart = noop;
  dragMove = noop;
  dragEnd = noop;
  showOrbMenu = noop;
  openPanel = noop;
  requestSync = noop;
  reportVisual = noop;
}

export const bridge: Bridge = api ? new ElectronBridge(api) : new BrowserBridge();
