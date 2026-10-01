import type { BBox } from "./contracts";
export function rotateBBox(box: BBox, rotation: number): BBox {
  const { x, y, width: w, height: h } = box;
  switch (rotation) {
    case 0: return box;
    case 90: return { x: 1-y-h, y: x, width: h, height: w };
    case 180: return { x: 1-x-w, y: 1-y-h, width: w, height: h };
    case 270: return { x: y, y: 1-x-w, width: h, height: w };
    default: throw new Error("Unsupported page rotation");
  }
}
