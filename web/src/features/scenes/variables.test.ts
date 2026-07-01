import { describe, it, expect } from "vitest";
import { collectVariables, seedSampleData, variableRegions } from "./variables";
import type { RequiredVariable, SceneDocument } from "@/api/types";

const doc: SceneDocument = {
  grid: [],
  render: {
    A: { bind: "line", as: "glyphs", color: "white", fill: { data: "badge_color" } },
    B: { bind: "time", as: "glyphs", color: { data: "time_color" } },
    C: { bind: "time", as: "text" },
  },
};

describe("collectVariables", () => {
  it("collects binds and {data} color/fill keys, tagging colors", () => {
    const vars = collectVariables(doc, []);
    const byName = Object.fromEntries(vars.map((v) => [v.name, v]));
    expect(Object.keys(byName).sort()).toEqual(["badge_color", "line", "time", "time_color"]);
    // fill {data} and color {data} keys are tagged color even without server metadata
    expect(byName.badge_color.kind).toBe("color");
    expect(byName.time_color.kind).toBe("color");
    expect(byName.line.kind).toBeUndefined();
  });

  it("prefers server metadata when present", () => {
    const server: RequiredVariable[] = [{ name: "time", kind: "text", required: true }];
    const vars = collectVariables(doc, server);
    expect(vars.find((v) => v.name === "time")).toEqual({ name: "time", kind: "text", required: true });
  });
});

describe("seedSampleData", () => {
  it("defaults colors to white(69) and numbers to 0, leaves text unset", () => {
    const vars: RequiredVariable[] = [
      { name: "c", kind: "color" },
      { name: "n", kind: "number" },
      { name: "t", kind: "text" },
    ];
    expect(seedSampleData(vars, {})).toEqual({ c: 69, n: 0 });
  });

  it("uses the user's value or fallback over the default", () => {
    const vars: RequiredVariable[] = [
      { name: "c", kind: "color", fallback: "5" },
      { name: "n", kind: "number" },
    ];
    expect(seedSampleData(vars, { n: 42 })).toEqual({ c: "5", n: 42 });
  });
});

describe("variableRegions", () => {
  it("maps each variable to the regions that reference it", () => {
    expect(variableRegions(doc)).toEqual({
      line: ["A"],
      badge_color: ["A"],
      time: ["B", "C"],
      time_color: ["B"],
    });
  });
});
