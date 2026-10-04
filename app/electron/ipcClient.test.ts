import { describe, expect, it, vi } from "vitest";
import { IpcClient, IpcError } from "./ipcClient";
import type { WsLike } from "./ipcClient";
import { encode, parse } from "./protocol";

class FakeWs implements WsLike {
  readyState = 0;
  sent: string[] = [];
  onopen: WsLike["onopen"] = null;
  onmessage: WsLike["onmessage"] = null;
  onclose: WsLike["onclose"] = null;
  onerror: WsLike["onerror"] = null;
  closed = false;
  constructor(readonly url: string) {}
  send(data: string) {
    this.sent.push(data);
  }
  close() {
    this.closed = true;
  }
  open() {
    this.onopen?.({});
  }
  receive(data: string) {
    this.onmessage?.({ data });
  }
  drop(code = 1006) {
    this.onclose?.({ code, reason: "" });
  }
}

function make() {
  const sockets: FakeWs[] = [];
  const client = new IpcClient((url) => {
    const ws = new FakeWs(url);
    sockets.push(ws);
    return ws;
  }, 200);
  return { client, sockets };
}

async function connected() {
  const { client, sockets } = make();
  const p = client.connect(4242, "tok");
  sockets[0].open();
  sockets[0].receive(encode("res", "hello", { ok: true }, "hello"));
  await p;
  return { client, ws: sockets[0] };
}

describe("IpcClient handshake", () => {
  it("connects to loopback only and sends hello with the token as the first message", async () => {
    const { client, sockets } = make();
    const p = client.connect(4242, "tok");
    expect(sockets[0].url).toBe("ws://127.0.0.1:4242/");
    sockets[0].open();
    const hello = parse(sockets[0].sent[0]);
    expect(hello).toMatchObject({ kind: "req", type: "hello", payload: { token: "tok" } });
    sockets[0].receive(encode("res", "hello", { ok: true }, "hello"));
    await p;
    expect(client.connected).toBe(true);
  });

  it("rejects with unauthorized when the service closes with 4401", async () => {
    const { client, sockets } = make();
    const p = client.connect(1, "bad");
    sockets[0].open();
    sockets[0].drop(4401);
    await expect(p).rejects.toMatchObject({ code: "unauthorized" });
    expect(client.connected).toBe(false);
  });

  it("rejects when the handshake does not answer in time", async () => {
    const { client, sockets } = make();
    const p = client.connect(1, "tok", 50);
    sockets[0].open();
    await expect(p).rejects.toMatchObject({ code: "timeout" });
    expect(sockets[0].closed).toBe(true);
  });

  it("rejects when the handshake response says not ok", async () => {
    const { client, sockets } = make();
    const p = client.connect(1, "tok");
    sockets[0].open();
    sockets[0].receive(encode("res", "hello", { ok: false, error: "unauthorized" }, "hello"));
    await expect(p).rejects.toBeInstanceOf(IpcError);
  });
});

describe("IpcClient session", () => {
  it("correlates responses by id and surfaces service errors", async () => {
    const { client, ws } = await connected();
    const ok = client.request("state.get");
    ws.receive(encode("res", "state.get", { ok: true, state: "IDLE" }, parse(ws.sent[1]).id));
    await expect(ok).resolves.toMatchObject({ state: "IDLE" });

    const bad = client.request("danger.run");
    ws.receive(encode("res", "danger.run", { ok: false, error: "unsupported" }, parse(ws.sent[2]).id));
    await expect(bad).rejects.toMatchObject({ code: "unsupported" });
  });

  it("times out requests and rejects pending ones when the connection drops", async () => {
    const { client, ws } = await connected();
    await expect(client.request("slow")).rejects.toMatchObject({ code: "timeout" });
    const pending = client.request("pending");
    ws.drop();
    await expect(pending).rejects.toMatchObject({ code: "closed" });
    expect(client.connected).toBe(false);
  });

  it("emits events from the service and drops malformed frames", async () => {
    const { client, ws } = await connected();
    const seen: string[] = [];
    client.on("event", (e) => seen.push(e.type));
    ws.receive(encode("evt", "state.changed", { state: "ERROR" }));
    ws.receive("garbage");
    ws.receive(JSON.stringify({ v: 9, kind: "evt", type: "x.y" }));
    expect(seen).toEqual(["state.changed"]);
  });

  it("emits close after an authenticated connection drops, and sendEvent then refuses", async () => {
    const { client, ws } = await connected();
    const closed = vi.fn();
    client.on("close", closed);
    ws.drop(1011);
    expect(closed).toHaveBeenCalledWith({ code: 1011, reason: "" });
    expect(() => client.sendEvent("activation.orb_clicked")).toThrow(IpcError);
  });

  it("sends fire-and-forget events as evt envelopes", async () => {
    const { client, ws } = await connected();
    client.sendEvent("activation.orb_clicked", { source: "orb" });
    expect(parse(ws.sent[1])).toMatchObject({ kind: "evt", type: "activation.orb_clicked", payload: { source: "orb" } });
  });
});
