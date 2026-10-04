// Envelope of the shell <-> service protocol (contracts/protocol.md, version 1).
export const PROTOCOL_VERSION = 1;
export const MAX_MESSAGE_BYTES = 1 << 20;

export type Kind = "req" | "res" | "evt";

export interface Envelope {
  v: number;
  kind: Kind;
  type: string;
  id?: string;
  ts?: number;
  payload: Record<string, unknown>;
}

const TYPE_RE = /^[a-z][a-z0-9_]*(\.[a-z0-9_]+)*$/;

export class ProtocolError extends Error {}

export function encode(kind: Kind, type: string, payload: Record<string, unknown> = {}, id?: string): string {
  const body: Envelope = { v: PROTOCOL_VERSION, kind, type, payload, ts: Date.now() / 1000 };
  if (id !== undefined) body.id = id;
  return JSON.stringify(body);
}

export function parse(raw: unknown): Envelope {
  if (typeof raw !== "string") throw new ProtocolError("text frames only");
  if (raw.length > MAX_MESSAGE_BYTES) throw new ProtocolError("message too large");
  let data: unknown;
  try {
    data = JSON.parse(raw);
  } catch {
    throw new ProtocolError("invalid JSON");
  }
  if (typeof data !== "object" || data === null || Array.isArray(data)) throw new ProtocolError("envelope must be an object");
  const e = data as Record<string, unknown>;
  if (e.v !== PROTOCOL_VERSION) throw new ProtocolError("unsupported protocol version");
  if (e.kind !== "req" && e.kind !== "res" && e.kind !== "evt") throw new ProtocolError("invalid kind");
  if (typeof e.type !== "string" || !TYPE_RE.test(e.type)) throw new ProtocolError("invalid type");
  if (e.id !== undefined && typeof e.id !== "string") throw new ProtocolError("id must be a string");
  if ((e.kind === "req" || e.kind === "res") && !e.id) throw new ProtocolError("req/res require an id");
  const payload = e.payload ?? {};
  if (typeof payload !== "object" || payload === null || Array.isArray(payload)) throw new ProtocolError("payload must be an object");
  return { v: 1, kind: e.kind, type: e.type, id: e.id as string | undefined, payload: payload as Record<string, unknown> };
}
