// Click vs drag: a small movement starts a window drag, otherwise it is a click.
export const DRAG_THRESHOLD_PX = 5;

export interface PointerStart {
  x: number;
  y: number;
}

export function isDrag(start: PointerStart, x: number, y: number): boolean {
  return Math.hypot(x - start.x, y - start.y) > DRAG_THRESHOLD_PX;
}
