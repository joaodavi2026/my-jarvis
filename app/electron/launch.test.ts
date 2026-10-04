import * as path from "node:path";
import { describe, expect, it } from "vitest";
import { resolveServiceLaunch } from "./launch";

const REPO = path.join("x", "repo");

describe("resolveServiceLaunch", () => {
  it("uses the repo venv and service/src by default", () => {
    const l = resolveServiceLaunch({}, REPO, () => true)!;
    expect(l.command).toBe(path.join(REPO, "service", ".venv", "Scripts", "python.exe"));
    expect(l.args).toEqual(["-m", "jarvis"]);
    expect(l.cwd).toBe(path.join(REPO, "service", "src"));
  });

  it("honours JARVIS_PYTHON and JARVIS_REPO_ROOT", () => {
    const l = resolveServiceLaunch({ JARVIS_PYTHON: "py.exe", JARVIS_REPO_ROOT: "other" }, REPO, () => true)!;
    expect(l.command).toBe("py.exe");
    expect(l.cwd).toBe(path.join("other", "service", "src"));
  });

  it("returns null when python or the service folder is missing", () => {
    expect(resolveServiceLaunch({}, REPO, () => false)).toBeNull();
  });

  it("never carries a token in args or env and strips ELECTRON_RUN_AS_NODE", () => {
    const l = resolveServiceLaunch({ ELECTRON_RUN_AS_NODE: "1", JARVIS_SESSION_TOKEN: "secret", KEEP: "1" }, REPO, () => true)!;
    expect(l.env.ELECTRON_RUN_AS_NODE).toBeUndefined();
    expect(l.env.JARVIS_SESSION_TOKEN).toBeUndefined();
    expect(l.env.KEEP).toBe("1");
    expect(l.args.join(" ")).not.toMatch(/token/i);
  });
});
