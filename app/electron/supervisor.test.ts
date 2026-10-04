import { EventEmitter } from "node:events";
import { PassThrough } from "node:stream";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ServiceSupervisor } from "./supervisor";
import type { ChildLike, ReadyInfo } from "./supervisor";

class FakeChild extends EventEmitter {
  static count = 0;
  pid = 1000 + FakeChild.count++;
  stdin = new PassThrough();
  stdout = new PassThrough();
  stderr = new PassThrough();
  exitCode: number | null = null;
  killed = false;
  written = "";
  stdinEnded = false;
  constructor() {
    super();
    this.stdin.on("data", (d: Buffer) => (this.written += d.toString()));
    this.stdin.on("end", () => (this.stdinEnded = true));
  }
  kill() {
    this.killed = true;
    this.die(null);
    return true;
  }
  die(code: number | null) {
    if (this.exitCode !== null) return;
    this.exitCode = code ?? -1;
    this.emit("exit", code, null);
  }
  say(line: string) {
    this.stdout.write(line + "\n");
  }
}

const LAUNCH = { command: "python.exe", args: ["-m", "jarvis"], cwd: "svc", env: { PATH: "x" } as NodeJS.ProcessEnv };

function setup(overrides: Partial<ConstructorParameters<typeof ServiceSupervisor>[0]> = {}) {
  const children: FakeChild[] = [];
  const calls: { command: string; args: string[]; env: NodeJS.ProcessEnv }[] = [];
  const supervisor = new ServiceSupervisor({
    launch: LAUNCH,
    readyTimeoutMs: 1000,
    stopGraceMs: 500,
    backoffMs: [100, 200, 400],
    maxAttempts: 3,
    spawnFn: (command, args, options) => {
      calls.push({ command, args, env: options.env });
      const child = new FakeChild();
      children.push(child);
      return child as unknown as ChildLike;
    },
    ...overrides,
  });
  const ready: ReadyInfo[] = [];
  const downs: { reason: string; willRestart: boolean }[] = [];
  const logs: string[] = [];
  supervisor.on("ready", (r: ReadyInfo) => ready.push(r));
  supervisor.on("down", (d) => downs.push(d));
  supervisor.on("log", (l: string) => logs.push(l));
  return { supervisor, children, calls, ready, downs, logs };
}

const flush = () => vi.advanceTimersByTimeAsync(0);
const readyLine = (port: number) => JSON.stringify({ ready: true, port, protocol: 1 });

beforeEach(() => vi.useFakeTimers());
afterEach(() => vi.useRealTimers());

describe("ServiceSupervisor bootstrap", () => {
  it("writes the token as the first stdin line, keeps stdin open, and never puts it in argv or env", async () => {
    const { supervisor, children, calls, ready } = setup();
    supervisor.start();
    await flush();
    const child = children[0];
    expect(child.written).toMatch(/^[0-9a-f]{64}\n$/);
    expect(child.stdinEnded).toBe(false);
    const token = child.written.trim();
    expect(JSON.stringify(calls[0].args)).not.toContain(token);
    expect(JSON.stringify(calls[0].env)).not.toContain(token);
    child.say(readyLine(43210));
    await flush();
    expect(ready).toEqual([{ port: 43210, token, pid: child.pid }]);
    expect(supervisor.currentState).toBe("READY");
  });

  it("ignores noise and invalid ready lines until a valid one arrives", async () => {
    const { supervisor, children, ready } = setup();
    supervisor.start();
    const child = children[0];
    const bad = ["hello", "{}", JSON.stringify({ ready: true }), JSON.stringify({ ready: true, port: 0 }),
      JSON.stringify({ ready: true, port: 70000 }), JSON.stringify({ ready: true, port: "80" }),
      JSON.stringify({ ready: false, port: 80 })];
    for (const line of bad) child.say(line);
    await flush();
    expect(ready).toHaveLength(0);
    child.say(readyLine(5000));
    await flush();
    expect(ready[0].port).toBe(5000);
  });

  it("redacts the token from forwarded stderr lines", async () => {
    const { supervisor, children, logs } = setup();
    supervisor.start();
    const child = children[0];
    const token = child.written.trim();
    child.stderr.write(`oops token=${token} end\n`);
    await flush();
    expect(logs.join("\n")).not.toContain(token);
    expect(logs.join("\n")).toContain("[redacted]");
  });
});

describe("ServiceSupervisor failures", () => {
  it("kills the child on ready timeout and retries with a NEW token after the backoff", async () => {
    const { supervisor, children, downs } = setup();
    supervisor.start();
    await vi.advanceTimersByTimeAsync(1000);
    expect(children[0].killed).toBe(true);
    expect(downs[0]).toMatchObject({ reason: "timeout", willRestart: true });
    expect(supervisor.currentState).toBe("BACKOFF");
    await vi.advanceTimersByTimeAsync(100);
    expect(children).toHaveLength(2);
    expect(children[1].written.trim()).not.toBe(children[0].written.trim());
  });

  it("restarts after a crash with growing backoff and resets the counter once ready", async () => {
    const { supervisor, children, downs } = setup();
    supervisor.start();
    children[0].say(readyLine(1111));
    await flush();
    children[0].die(1);
    await vi.advanceTimersByTimeAsync(100);
    expect(children).toHaveLength(2);
    children[1].die(1);
    await vi.advanceTimersByTimeAsync(199);
    expect(children).toHaveLength(2);
    await vi.advanceTimersByTimeAsync(1);
    expect(children).toHaveLength(3);
    expect(downs.map((d) => d.reason)).toEqual(["exit", "exit"]);
  });

  it("gives up after maxAttempts and reports FAILED", async () => {
    const { supervisor, children } = setup();
    const failed = vi.fn();
    supervisor.on("failed", failed);
    supervisor.start();
    for (let i = 0; i < 10 && supervisor.currentState !== "FAILED"; i++) {
      children[children.length - 1].die(2);
      await vi.advanceTimersByTimeAsync(500);
    }
    expect(supervisor.currentState).toBe("FAILED");
    expect(failed).toHaveBeenCalledOnce();
    expect(children.length).toBeLessThanOrEqual(4);
  });

  it("treats a spawn error such as python not found as a failure with backoff", async () => {
    const { supervisor, downs } = setup({
      spawnFn: () => {
        throw new Error("ENOENT");
      },
    });
    supervisor.start();
    await flush();
    expect(downs[0]).toMatchObject({ reason: "error", willRestart: true });
  });
});

describe("ServiceSupervisor shutdown", () => {
  it("stop() closes stdin, waits for the child to exit, and does not restart", async () => {
    const { supervisor, children } = setup();
    supervisor.start();
    children[0].say(readyLine(2222));
    await flush();
    const stopping = supervisor.stop();
    await flush();
    expect(children[0].stdinEnded).toBe(true);
    expect(children[0].killed).toBe(false);
    children[0].die(0);
    await stopping;
    expect(supervisor.currentState).toBe("STOPPED");
    await vi.advanceTimersByTimeAsync(5000);
    expect(children).toHaveLength(1);
  });

  it("stop() force-kills a child that ignores the stdin EOF after the grace period", async () => {
    const { supervisor, children } = setup();
    supervisor.start();
    children[0].say(readyLine(3333));
    await flush();
    const stopping = supervisor.stop();
    await vi.advanceTimersByTimeAsync(500);
    expect(children[0].killed).toBe(true);
    await vi.advanceTimersByTimeAsync(600);
    await stopping;
    expect(supervisor.currentState).toBe("STOPPED");
  });

  it("restart() replaces the child immediately with a fresh token", async () => {
    const { supervisor, children } = setup();
    supervisor.start();
    children[0].say(readyLine(4444));
    await flush();
    const restarting = supervisor.restart();
    await flush();
    children[0].die(0);
    await restarting;
    expect(children).toHaveLength(2);
    expect(children[1].written.trim()).not.toBe(children[0].written.trim());
  });

  it("stop() during backoff cancels the pending restart", async () => {
    const { supervisor, children } = setup();
    supervisor.start();
    children[0].die(1);
    await flush();
    expect(supervisor.currentState).toBe("BACKOFF");
    await supervisor.stop();
    await vi.advanceTimersByTimeAsync(5000);
    expect(children).toHaveLength(1);
  });
});
