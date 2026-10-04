import { describe, expect, it } from "vitest";
import { encode, parse, ProtocolError } from "./protocol";

describe("protocol envelope", () => {
  it("round-trips requests and events", () => {
    const req = parse(encode("req", "ping", {}, "1"));
    expect(req).toMatchObject({ kind: "req", type: "ping", id: "1" });
    const evt = parse(encode("evt", "activation.orb_clicked", { source: "orb" }));
    expect(evt.payload).toEqual({ source: "orb" });
  });

  it.each([
    "not json", "[]", "42", JSON.stringify({ v: 2, kind: "evt", type: "a.b" }),
    JSON.stringify({ v: 1, kind: "cmd", type: "a.b" }), JSON.stringify({ v: 1, kind: "evt", type: "Bad Type" }),
    JSON.stringify({ v: 1, kind: "req", type: "ping" }), JSON.stringify({ v: 1, kind: "evt", type: "a.b", payload: [1] }),
    JSON.stringify({ v: 1, kind: "evt", type: "a.b", id: 7 }),
  ])("rejects malformed envelope %#", (raw) => {
    expect(() => parse(raw)).toThrow(ProtocolError);
  });

  it("rejects binary and oversized frames", () => {
    expect(() => parse(new Uint8Array(2))).toThrow(ProtocolError);
    expect(() => parse(JSON.stringify({ v: 1, kind: "evt", type: "a.b", payload: { x: "a".repeat(1 << 20) } }))).toThrow(ProtocolError);
  });
});
