import { describe, expect, it } from "vitest";
import { rotateBBox } from "./coordinates";
describe("PDF projection contract", () => {
  const box = { x:.1, y:.2, width:.2, height:.2 };
  it.each([
    [0, [.1,.2,.2,.2]], [90, [.6,.1,.2,.2]],
    [180, [.7,.6,.2,.2]], [270, [.2,.7,.2,.2]],
  ])("rotation %s", (angle, values) => {
    Object.values(rotateBBox(box, angle as number)).forEach((v,i) =>
      expect(v).toBeCloseTo((values as number[])[i]));
  });
  it("rejects unknown rotations", () => expect(() => rotateBBox(box, 45)).toThrow());
});
