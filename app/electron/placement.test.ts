import { describe, expect, it } from "vitest";
import { cornerPosition, isCorner, visiblePosition } from "./placement";

const AREA = { x: 0, y: 0, width: 1920, height: 1040 };
const SIZE = { width: 160, height: 160 };

describe("cornerPosition", () => {
  it("puts the visible orb `margin` px from the corner", () => {
    const p = cornerPosition(AREA, SIZE, 64, "bottom-right", 12);
    expect(p.x + 48 + 64).toBe(1920 - 12);
    expect(p.y + 48 + 64).toBe(1040 - 12);
  });
  it("handles all four corners and offset monitors", () => {
    expect(cornerPosition(AREA, SIZE, 64, "top-left", 12)).toEqual({ x: -36, y: -36 });
    expect(cornerPosition(AREA, SIZE, 64, "top-right", 12).y).toBe(-36);
    expect(cornerPosition(AREA, SIZE, 64, "bottom-left", 12).x).toBe(-36);
    const left = { x: -1920, y: 0, width: 1920, height: 1080 };
    expect(cornerPosition(left, SIZE, 64, "bottom-right", 12).x).toBeLessThan(0);
  });
});

describe("visiblePosition", () => {
  it("keeps a visible saved position", () => expect(visiblePosition([AREA], { x: 500, y: 400 }, SIZE)).toEqual({ x: 500, y: 400 }));
  it("rejects a position on a removed monitor", () => {
    expect(visiblePosition([AREA], { x: -1700, y: 300 }, SIZE)).toBeNull();
    expect(visiblePosition([], { x: 10, y: 10 }, SIZE)).toBeNull();
  });
  it("clamps a partially off-screen position", () => {
    expect(visiblePosition([AREA], { x: 1800, y: 950 }, SIZE)).toEqual({ x: 1760, y: 880 });
    expect(visiblePosition([AREA], { x: 1900, y: 1030 }, SIZE)).toBeNull();
    expect(visiblePosition([AREA], { x: -60, y: -60 }, SIZE)).toEqual({ x: 0, y: 0 });
  });
});

describe("isCorner", () => {
  it("validates corner names", () => {
    expect(isCorner("top-left")).toBe(true);
    expect(isCorner("middle")).toBe(false);
    expect(isCorner(3)).toBe(false);
  });
});
