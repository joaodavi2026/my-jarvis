import { describe, expect, it } from "vitest";
import { DRAG_THRESHOLD_PX, isDrag } from "./gesture";

describe("isDrag", () => {
  it("treats tiny jitter as a click and real movement as a drag", () => {
    expect(isDrag({ x: 10, y: 10 }, 12, 11)).toBe(false);
    expect(isDrag({ x: 10, y: 10 }, 10 + DRAG_THRESHOLD_PX, 10)).toBe(false);
    expect(isDrag({ x: 10, y: 10 }, 20, 10)).toBe(true);
  });
});
