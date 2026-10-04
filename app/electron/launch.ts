// How the shell starts the Python service. The session token is never part of the launch spec.
import * as fs from "node:fs";
import * as path from "node:path";

export interface ServiceLaunch {
  command: string;
  args: string[];
  cwd: string;
  env: NodeJS.ProcessEnv;
}

/** Dev layout: <repo>/service/.venv + <repo>/service/src. Env overrides: JARVIS_PYTHON, JARVIS_REPO_ROOT. */
export function resolveServiceLaunch(
  baseEnv: NodeJS.ProcessEnv,
  repoRootGuess: string,
  exists: (p: string) => boolean = fs.existsSync,
): ServiceLaunch | null {
  const repoRoot = baseEnv.JARVIS_REPO_ROOT || repoRootGuess;
  const python = baseEnv.JARVIS_PYTHON || path.join(repoRoot, "service", ".venv", "Scripts", "python.exe");
  const cwd = path.join(repoRoot, "service", "src");
  if (!exists(python) || !exists(cwd)) return null;
  const env: NodeJS.ProcessEnv = { ...baseEnv, PYTHONUNBUFFERED: "1", PYTHONIOENCODING: "utf-8" };
  delete env.ELECTRON_RUN_AS_NODE;
  for (const key of Object.keys(env)) {
    if (/^(JARVIS_SESSION_TOKEN|JARVIS_TOKEN)$/i.test(key)) delete env[key]; // never inherit a token
  }
  return { command: python, args: ["-m", "jarvis"], cwd, env };
}
