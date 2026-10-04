// Authenticated WebSocket client for the Python service (ADR-0002). Runs in the Electron main process only:
// the renderer never sees the port or the token.
import { EventEmitter } from "node:events";
import { encode, parse } from "./protocol";
import type { Envelope } from "./protocol";

export interface WsLike {
  readyState: number;
  send(data: string): void;
  close(code?: number, reason?: string): void;
  onopen: ((ev: unknown) => void) | null;
  onmessage: ((ev: { data: unknown }) => void) | null;
  onclose: ((ev: { code: number; reason: string }) => void) | null;
  onerror: ((ev: unknown) => void) | null;
}

export type WsFactory = (url: string) => WsLike;

const defaultFactory: WsFactory = (url) => new (globalThis as unknown as { WebSocket: new (u: string) => WsLike }).WebSocket(url);

export class IpcError extends Error {
  constructor(message: string, readonly code: string) {
    super(message);
  }
}

interface Pending {
  resolve: (payload: Record<string, unknown>) => void;
  reject: (err: Error) => void;
  timer: NodeJS.Timeout;
}

export class IpcClient extends EventEmitter {
  private ws: WsLike | null = null;
  private pending = new Map<string, Pending>();
  private nextId = 1;
  private authenticated = false;

  constructor(
    private readonly factory: WsFactory = defaultFactory,
    private readonly requestTimeoutMs = 5000,
  ) {
    super();
  }

  get connected(): boolean {
    return this.authenticated;
  }

  /** Opens the socket and performs the hello{token} handshake. Rejects if the service refuses or closes. */
  connect(port: number, token: string, handshakeTimeoutMs = 3000): Promise<void> {
    return new Promise((resolve, reject) => {
      const ws = this.factory("ws://127.0.0.1:" + port + "/");
      this.ws = ws;
      let settled = false;
      const fail = (err: Error) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        try {
          ws.close();
        } catch {
          /* already closed */
        }
        reject(err);
      };
      const timer = setTimeout(() => fail(new IpcError("handshake timed out", "timeout")), handshakeTimeoutMs);
      ws.onopen = () => ws.send(encode("req", "hello", { token }, "hello"));
      ws.onerror = () => fail(new IpcError("connection error", "connection"));
      ws.onclose = (ev) => {
        const wasAuthenticated = this.authenticated;
        this.authenticated = false;
        this.rejectAll(new IpcError("connection closed", "closed"));
        fail(new IpcError("closed before authentication (code " + ev.code + ")", ev.code === 4401 ? "unauthorized" : "closed"));
        if (wasAuthenticated) this.emit("close", { code: ev.code, reason: ev.reason });
      };
      ws.onmessage = (ev) => {
        let message: Envelope;
        try {
          message = parse(ev.data);
        } catch {
          return; // a malformed frame from the service is dropped, never trusted
        }
        if (!this.authenticated) {
          if (message.kind === "res" && message.id === "hello") {
            if (message.payload.ok === true) {
              this.authenticated = true;
              settled = true;
              clearTimeout(timer);
              resolve();
            } else fail(new IpcError("service rejected the handshake", "unauthorized"));
          }
          return;
        }
        this.dispatch(message);
      };
    });
  }

  request(type: string, payload: Record<string, unknown> = {}): Promise<Record<string, unknown>> {
    return new Promise((resolve, reject) => {
      if (!this.ws || !this.authenticated) return reject(new IpcError("not connected", "closed"));
      const id = String(this.nextId++);
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new IpcError("request " + type + " timed out", "timeout"));
      }, this.requestTimeoutMs);
      this.pending.set(id, { resolve, reject, timer });
      this.ws.send(encode("req", type, payload, id));
    });
  }

  /** Fire-and-forget event to the service. The service only accepts allow-listed types. */
  sendEvent(type: string, payload: Record<string, unknown> = {}): void {
    if (!this.ws || !this.authenticated) throw new IpcError("not connected", "closed");
    this.ws.send(encode("evt", type, payload));
  }

  close(): void {
    this.authenticated = false;
    this.rejectAll(new IpcError("client closed", "closed"));
    try {
      this.ws?.close(1000, "bye");
    } catch {
      /* ignore */
    }
    this.ws = null;
  }

  private dispatch(message: Envelope): void {
    if (message.kind === "res" && message.id) {
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      clearTimeout(pending.timer);
      if (message.payload.ok === false) {
        const code = String(message.payload.error ?? "error");
        pending.reject(new IpcError(code, code));
      } else pending.resolve(message.payload);
    } else if (message.kind === "evt") {
      this.emit("event", message);
    }
  }

  private rejectAll(err: Error): void {
    for (const [, p] of this.pending) {
      clearTimeout(p.timer);
      p.reject(err);
    }
    this.pending.clear();
  }
}
