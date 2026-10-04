// Shell-owned window preferences (orb corner and position). UI preferences only: no secrets, no user data.
import * as fs from "node:fs";
import * as path from "node:path";
import { isCorner } from "./placement";
import type { Corner } from "./placement";

export interface Prefs {
  orbCorner: Corner;
  orbPosition: { x: number; y: number } | null;
}

export const defaultPrefs = (): Prefs => ({ orbCorner: "bottom-right", orbPosition: null });

const isFiniteNumber = (v: unknown): v is number => typeof v === "number" && Number.isFinite(v);

/** Missing file -> defaults. Corrupt file -> defaults, the broken file is kept aside (never deleted). */
export function loadPrefs(file: string): Prefs {
  let text: string;
  try {
    text = fs.readFileSync(file, "utf8");
  } catch {
    return defaultPrefs();
  }
  try {
    const data = JSON.parse(text) as Record<string, unknown>;
    if (typeof data !== "object" || data === null || Array.isArray(data)) throw new Error("not an object");
    const prefs = defaultPrefs();
    if (isCorner(data.orbCorner)) prefs.orbCorner = data.orbCorner;
    const pos = data.orbPosition as { x?: unknown; y?: unknown } | null | undefined;
    if (pos && isFiniteNumber(pos.x) && isFiniteNumber(pos.y)) prefs.orbPosition = { x: pos.x, y: pos.y };
    return prefs;
  } catch {
    try {
      fs.renameSync(file, `${file}.corrupt`);
    } catch {
      /* keep going with defaults */
    }
    return defaultPrefs();
  }
}

/** Atomic save: temp file next to the target, then rename over it. */
export function savePrefs(file: string, prefs: Prefs): void {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  const tmp = `${file}.tmp`;
  fs.writeFileSync(tmp, JSON.stringify(prefs, null, 2));
  fs.renameSync(tmp, file);
}
