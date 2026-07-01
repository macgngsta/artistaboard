import { describe, it, expect } from "vitest";
import { charForCode, colorForCode, isColorCode, COLOR_NAME_TO_CODE } from "./codes";

describe("charForCode", () => {
  it("maps blank, letters, and digits per the backend table", () => {
    expect(charForCode(0)).toBe(" ");
    expect(charForCode(1)).toBe("A");
    expect(charForCode(26)).toBe("Z");
    expect(charForCode(27)).toBe("1");
    expect(charForCode(35)).toBe("9");
    expect(charForCode(36)).toBe("0");
  });

  it("maps punctuation and renders unmapped codes as blank", () => {
    expect(charForCode(37)).toBe("!");
    expect(charForCode(62)).toBe("°");
    expect(charForCode(43)).toBe(" "); // gap in the table
    expect(charForCode(58)).toBe(" ");
  });
});

describe("color codes", () => {
  it("identifies the 63–71 color chip range", () => {
    expect(isColorCode(62)).toBe(false);
    expect(isColorCode(63)).toBe(true);
    expect(isColorCode(71)).toBe(true);
    expect(isColorCode(72)).toBe(false);
  });

  it("returns hex for chips and null for glyph codes", () => {
    expect(colorForCode(63)).toBe("#ff0000");
    expect(colorForCode(69)).toBe("#ffffff");
    expect(colorForCode(1)).toBeNull();
  });

  it("resolves names to codes (violet/purple alias)", () => {
    expect(COLOR_NAME_TO_CODE.yellow).toBe(65);
    expect(COLOR_NAME_TO_CODE.purple).toBe(COLOR_NAME_TO_CODE.violet);
  });
});
