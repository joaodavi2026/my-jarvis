// Runs in the sandboxed preload context. Exposes a minimal, explicit API; the renderer gets no Node access,
// no service port and no token.
import { contextBridge, ipcRenderer } from "electron";

type Unlisten = () => void;

function listen<T>(channel: string, cb: (payload: T) => void): Unlisten {
  const handler = (_event: unknown, payload: T) => cb(payload);
  ipcRenderer.on(channel, handler);
  return () => {
    ipcRenderer.removeListener(channel, handler);
  };
}

contextBridge.exposeInMainWorld("jarvis", {
  onBackendEvent: (cb: (e: unknown) => void) => listen("jarvis:event", cb),
  onAction: (cb: (a: unknown) => void) => listen("jarvis:action", cb),
  onMenu: (cb: (action: string) => void) => listen("jarvis:menu", cb),
  broadcastAction: (action: unknown) => ipcRenderer.send("jarvis:broadcast-action", action),
  send: (type: string, payload?: Record<string, unknown>) => ipcRenderer.invoke("jarvis:send", type, payload ?? {}),
  dragStart: (screenX: number, screenY: number) => ipcRenderer.send("orb:drag-start", screenX, screenY),
  dragMove: (screenX: number, screenY: number) => ipcRenderer.send("orb:drag-move", screenX, screenY),
  dragEnd: () => ipcRenderer.send("orb:drag-end"),
  showOrbMenu: () => ipcRenderer.send("orb:menu"),
  openPanel: () => ipcRenderer.send("panel:open"),
  reportVisual: (state: string) => ipcRenderer.send("e2e:visual", state),
  requestSync: () => ipcRenderer.send("jarvis:sync"),
});
