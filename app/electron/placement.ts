// Pure geometry for the orb window. All values are physical/DIP pixels from the same coordinate space.
export type Corner = "top-left" | "top-right" | "bottom-left" | "bottom-right";
export const CORNERS: readonly Corner[] = ["top-left", "top-right", "bottom-left", "bottom-right"];

export interface Rect {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** Top-left of a window of `size` whose visible orb (`core` px, centred) is `margin` px from the corner. */
export function cornerPosition(area: Rect, size: { width: number; height: number }, core: number, corner: Corner, margin: number) {
  const padX = Math.floor((size.width - core) / 2);
  const padY = Math.floor((size.height - core) / 2);
  const x = corner.endsWith("left") ? area.x + margin - padX : area.x + area.width - margin - core - padX;
  const y = corner.startsWith("top") ? area.y + margin - padY : area.y + area.height - margin - core - padY;
  return { x, y };
}

/** A saved position is reused only if the window centre is still on a display; it is clamped inside it. */
export function visiblePosition(areas: Rect[], pos: { x: number; y: number }, size: { width: number; height: number }) {
  const cx = pos.x + size.width / 2;
  const cy = pos.y + size.height / 2;
  const area = areas.find((a) => cx >= a.x && cx < a.x + a.width && cy >= a.y && cy < a.y + a.height);
  if (!area) return null;
  const clamp = (v: number, lo: number, hi: number) => Math.min(Math.max(v, lo), Math.max(lo, hi));
  return { x: clamp(pos.x, area.x, area.x + area.width - size.width), y: clamp(pos.y, area.y, area.y + area.height - size.height) };
}

export const isCorner = (v: unknown): v is Corner => typeof v === "string" && (CORNERS as readonly string[]).includes(v);
