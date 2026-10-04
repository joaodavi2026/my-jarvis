import * as fs from "node:fs";
import * as os from "node:os";
import * as path from "node:path";
import { beforeEach, describe, expect, it } from "vitest";
import { defaultPrefs, loadPrefs, savePrefs } from "./prefs";

let dir: string;
beforeEach(() => {
  dir = fs.mkdtempSync(path.join(os.tmpdir(), "jarvis-prefs-"));
});

describe("prefs", () => {
  it("missing file gives defaults", () => expect(loadPrefs(path.join(dir, "p.json"))).toEqual(defaultPrefs()));

  it("round-trips atomically", () => {
    const file = path.join(dir, "p.json");
    savePrefs(file, { orbCorner: "top-left", orbPosition: { x: 10, y: -20 } });
    expect(loadPrefs(file)).toEqual({ orbCorner: "top-left", orbPosition: { x: 10, y: -20 } });
    expect(fs.existsSync(`${file}.tmp`)).toBe(false);
  });

  it("sets a corrupt file aside instead of deleting it", () => {
    const file = path.join(dir, "p.json");
    fs.writeFileSync(file, "{nope");
    expect(loadPrefs(file)).toEqual(defaultPrefs());
    expect(fs.existsSync(`${file}.corrupt`)).toBe(true);
  });

  it("ignores invalid values field by field", () => {
    const file = path.join(dir, "p.json");
    fs.writeFileSync(file, JSON.stringify({ orbCorner: "middle", orbPosition: { x: "a", y: 1 }, future: true }));
    expect(loadPrefs(file)).toEqual(defaultPrefs());
    fs.writeFileSync(file, JSON.stringify({ orbCorner: "top-right", orbPosition: { x: 5, y: 6 } }));
    expect(loadPrefs(file)).toEqual({ orbCorner: "top-right", orbPosition: { x: 5, y: 6 } });
  });
});
