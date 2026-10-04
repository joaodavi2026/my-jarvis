// Supervises the Python service. Bootstrap (contracts/protocol.md):
//   token -> child's stdin as the first line (stdin stays open: EOF tells the service to exit)
//   child -> stdout: one JSON line {"ready":true,"port":N,"protocol":1} (never the token)
// The token lives only in memory: not in argv, not in env, not in logs, not on disk.
import { randomBytes } from "node:crypto";
import { EventEmitter } from "node:events";
import { spawn as nodeSpawn } from "node:child_process";
import type { Readable, Writable } from "node:stream";
import type { ServiceLaunch } from "./launch";

export interface ChildLike {
  pid?: number;
  stdin: Writable | null;
  stdout: Readable | null;
  stderr: Readable | null;
  exitCode: number | null;
  on(event: "exit", cb: (code: number | null, signal: string | null) => void): unknown;
  on(event: "error", cb: (err: Error) => void): unknown;
  kill(): boolean;
}

export type SpawnFn = (command: string, args: string[], options: { cwd: string; env: NodeJS.ProcessEnv }) => ChildLike;
export type SupervisorState = "STOPPED" | "STARTING" | "READY" | "BACKOFF" | "STOPPING" | "FAILED";

export interface SupervisorOptions {
  launch: ServiceLaunch;
  spawnFn?: SpawnFn;
  readyTimeoutMs?: number;
  stopGraceMs?: number;
  backoffMs?: number[];
  maxAttempts?: number;
}

export interface ReadyInfo {
  port: number;
  token: string;
  pid: number;
}

const defaultSpawn: SpawnFn = (command, args, options) =>
  nodeSpawn(command, args, { ...options, stdio: ["pipe", "pipe", "pipe"], windowsHide: true }) as unknown as ChildLike;

export class ServiceSupervisor extends EventEmitter {
  private state: SupervisorState = "STOPPED";
  private child: ChildLike | null = null;
  private token = "";
  private attempt = 0;
  private generation = 0;
  private readyTimer: NodeJS.Timeout | null = null;
  private restartTimer: NodeJS.Timeout | null = null;
  private readonly opts: Required<Omit<SupervisorOptions, "launch" | "spawnFn">> & { launch: ServiceLaunch; spawnFn: SpawnFn };

  constructor(options: SupervisorOptions) {
    super();
    this.opts = {
      readyTimeoutMs: 15_000,
      stopGraceMs: 5_000,
      backoffMs: [1_000, 2_000, 4_000, 8_000, 16_000],
      maxAttempts: 5,
      spawnFn: defaultSpawn,
      ...options,
    };
  }

  get currentState(): SupervisorState {
    return this.state;
  }

  get pid(): number | undefined {
    return this.child?.pid;
  }

  start(): void {
    if (this.state !== "STOPPED" && this.state !== "FAILED" && this.state !== "BACKOFF") return;
    this.clearRestartTimer();
    this.spawnChild();
  }

  /** Clean shutdown: close stdin (service exits by itself), wait, then kill if it does not. */
  async stop(): Promise<void> {
    this.clearRestartTimer();
    if (this.state === "STOPPING") return;
    const child = this.child;
    this.setState("STOPPING");
    this.generation++;
    this.clearReadyTimer();
    if (child && child.exitCode === null) await this.terminate(child);
    this.child = null;
    this.setState("STOPPED");
  }

  /** Restart now, without backoff (user chose "Restart service"). */
  async restart(): Promise<void> {
    await this.stop();
    this.attempt = 0;
    this.start();
  }

  private spawnChild(): void {
    this.token = randomBytes(32).toString("hex");
    const token = this.token;
    const generation = ++this.generation;
    this.setState("STARTING");
    let child: ChildLike;
    try {
      child = this.opts.spawnFn(this.opts.launch.command, this.opts.launch.args, {
        cwd: this.opts.launch.cwd,
        env: this.opts.launch.env,
      });
    } catch (err) {
      this.onDown(generation, "error", null, (err as Error).message);
      return;
    }
    this.child = child;
    child.on("error", (err) => this.onDown(generation, "error", null, err.message));
    child.on("exit", (code) => {
      this.emit("exited", { code, pid: child.pid });
      this.onDown(generation, "exit", code);
    });
    child.stderr?.setEncoding?.("utf8");
    child.stderr?.on("data", (chunk: string) => {
      for (const line of String(chunk).split(/\r?\n/)) if (line) this.emit("log", line.split(token).join("[redacted]"));
    });
    this.readLines(child, generation, token);
    child.stdin?.on("error", () => {}); // the child may die while we write; exit handling covers it
    child.stdin?.write(`${token}\n`);
    this.readyTimer = setTimeout(() => {
      if (generation !== this.generation || this.state !== "STARTING") return;
      this.emit("log", "service did not report ready in time; stopping it");
      const stuck = this.child;
      this.onDown(generation, "timeout", null); // record the real reason first: kill() emits an exit event
      stuck?.kill();
    }, this.opts.readyTimeoutMs);
  }

  private readLines(child: ChildLike, generation: number, token: string): void {
    let buffer = "";
    child.stdout?.setEncoding?.("utf8");
    child.stdout?.on("data", (chunk: string) => {
      buffer += chunk;
      let index: number;
      while ((index = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, index).trim();
        buffer = buffer.slice(index + 1);
        if (generation === this.generation && this.state === "STARTING") this.handleReadyLine(line, child, token);
      }
    });
  }

  private handleReadyLine(line: string, child: ChildLike, token: string): void {
    let data: { ready?: unknown; port?: unknown };
    try {
      data = JSON.parse(line);
    } catch {
      return; // not the ready line
    }
    const port = data.port;
    if (data.ready !== true || typeof port !== "number" || !Number.isInteger(port) || port < 1 || port > 65535) return;
    this.clearReadyTimer();
    this.attempt = 0;
    this.setState("READY");
    this.emit("ready", { port, token, pid: child.pid ?? -1 } satisfies ReadyInfo);
  }

  private onDown(generation: number, reason: "exit" | "error" | "timeout", code: number | null, detail?: string): void {
    if (generation !== this.generation) return; // stale event from a previous child
    this.clearReadyTimer();
    if (this.state === "STOPPING" || this.state === "STOPPED") return;
    this.child = null;
    this.generation++; // ignore any later event of this child
    const exhausted = this.attempt >= this.opts.maxAttempts;
    this.emit("down", { reason, code, detail: detail ?? "", willRestart: !exhausted });
    if (exhausted) {
      this.setState("FAILED");
      this.emit("failed", { reason });
      return;
    }
    const delay = this.opts.backoffMs[Math.min(this.attempt, this.opts.backoffMs.length - 1)];
    this.attempt++;
    this.setState("BACKOFF");
    this.restartTimer = setTimeout(() => {
      this.restartTimer = null;
      if (this.state === "BACKOFF") this.spawnChild();
    }, delay);
  }

  private terminate(child: ChildLike): Promise<void> {
    return new Promise((resolve) => {
      let done = false;
      const finish = () => {
        if (done) return;
        done = true;
        clearTimeout(grace);
        resolve();
      };
      const grace = setTimeout(() => {
        child.kill();
        setTimeout(finish, 500);
      }, this.opts.stopGraceMs);
      child.on("exit", finish);
      try {
        child.stdin?.end();
      } catch {
        child.kill();
      }
    });
  }

  private setState(state: SupervisorState): void {
    this.state = state;
    this.emit("state", state);
  }

  private clearReadyTimer(): void {
    if (this.readyTimer) clearTimeout(this.readyTimer);
    this.readyTimer = null;
  }

  private clearRestartTimer(): void {
    if (this.restartTimer) clearTimeout(this.restartTimer);
    this.restartTimer = null;
  }
}
