// The webview talks only to the Rust shell (Tauri IPC). It never sees the service token or port.
import type { Action } from "../state/store";

export interface BackendEvent {
  type: string;
  payload?: Record<string, unknown>;
}

export type Unlisten = () => void;

export interface Bridge {
  readonly kind: "tauri" | "browser";
  /** Events forwarded by the shell from the Python service (allow-listed UI events). */
  onBackendEvent(cb: (e: BackendEvent) => void): Promise<Unlisten>;
  /** Reducer actions broadcast between the app windows (used by the dev simulator). */
  onAction(cb: (a: Action) => void): Promise<Unlisten>;
  broadcastAction(a: Action): Promise<void>;
  /** Menu choices made in the native orb context menu / tray. */
  onMenu(cb: (action: string) => void): Promise<Unlisten>;
  send(type: string, payload?: Record<string, unknown>): Promise<void>;
  startDragging(): Promise<void>;
  showOrbMenu(): Promise<void>;
  openPanel(): Promise<void>;
}

const hasTauri = typeof window !== "undefined" && "__TAURI_INTERNALS__" in window;

class BrowserBridge implements Bridge {
  readonly kind = "browser" as const;
  private channel = typeof BroadcastChannel !== "undefined" ? new BroadcastChannel("jarvis-dev") : null;

  async onBackendEvent(): Promise<Unlisten> {
    return () => {};
  }
  async onAction(cb: (a: Action) => void): Promise<Unlisten> {
    const handler = (ev: MessageEvent) => cb(ev.data as Action);
    this.channel?.addEventListener("message", handler);
    return () => this.channel?.removeEventListener("message", handler);
  }
  async broadcastAction(a: Action): Promise<void> {
    this.channel?.postMessage(a);
  }
  async onMenu(): Promise<Unlisten> {
    return () => {};
  }
  async send(): Promise<void> {}
  async startDragging(): Promise<void> {}
  async showOrbMenu(): Promise<void> {}
  async openPanel(): Promise<void> {}
}

class TauriBridge implements Bridge {
  readonly kind = "tauri" as const;

  private async listen<T>(name: string, cb: (payload: T) => void): Promise<Unlisten> {
    const { listen } = await import("@tauri-apps/api/event");
    return listen<T>(name, (event) => cb(event.payload));
  }
  onBackendEvent(cb: (e: BackendEvent) => void) {
    return this.listen<BackendEvent>("jarvis://event", cb);
  }
  onAction(cb: (a: Action) => void) {
    return this.listen<Action>("jarvis://action", cb);
  }
  async broadcastAction(a: Action) {
    const { emit } = await import("@tauri-apps/api/event");
    await emit("jarvis://action", a);
  }
  onMenu(cb: (action: string) => void) {
    return this.listen<string>("jarvis://menu", cb);
  }
  async send(type: string, payload?: Record<string, unknown>) {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("send_to_service", { message: { type, payload: payload ?? {} } });
  }
  async startDragging() {
    const { getCurrentWindow } = await import("@tauri-apps/api/window");
    await getCurrentWindow().startDragging();
  }
  async showOrbMenu() {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("show_orb_menu");
  }
  async openPanel() {
    const { invoke } = await import("@tauri-apps/api/core");
    await invoke("open_panel");
  }
}

export const bridge: Bridge = hasTauri ? new TauriBridge() : new BrowserBridge();
