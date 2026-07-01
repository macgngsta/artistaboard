import { describe, it, expect, beforeEach } from "vitest";
import { useSceneEditor, regionList, regionColor } from "./store";
import type { Scene } from "@/api/types";

const blankGrid = () => Array.from({ length: 6 }, () => ".".repeat(22));

function scene(overrides: Partial<Scene> = {}): Scene {
  return {
    id: "s1",
    owner_id: "u1",
    name: "Test",
    description: "",
    model: "flagship",
    rows: 6,
    cols: 22,
    is_system: false,
    document: { grid: blankGrid(), render: { A: { bind: "x" } } },
    required_variables: [],
    ...overrides,
  };
}

const st = () => useSceneEditor.getState();

describe("scene editor store", () => {
  beforeEach(() => st().load(scene()));

  it("paints the selected region into a cell, and erases to a filler", () => {
    st().selectRegion("A");
    st().setCell(0, 0);
    expect(st().document.grid[0][0]).toBe("A");

    st().setEraseMode(true);
    st().setCell(0, 0);
    expect(st().document.grid[0][0]).toBe(".");
  });

  it("does not paint when the scene is read-only (system)", () => {
    st().load(scene({ is_system: true }));
    st().selectRegion("A");
    st().setCell(0, 0);
    expect(st().document.grid[0][0]).toBe(".");
  });

  it("addRegion assigns the next free letter and selects it", () => {
    st().addRegion(); // A exists in render → next is B
    expect(st().selectedRegion).toBe("B");
    expect(regionList(st().document)).toContain("B");
  });

  it("removeRegion clears its cells and render config", () => {
    st().selectRegion("A");
    st().setCell(1, 1);
    expect(st().document.grid[1][1]).toBe("A");

    st().removeRegion("A");
    expect(st().document.grid[1][1]).toBe(".");
    expect(st().document.render?.A).toBeUndefined();
  });

  it("regionList unions grid letters and render keys", () => {
    // B is painted but has no render entry; A has a render entry but no cells
    const grid = blankGrid();
    grid[0] = "B" + ".".repeat(21);
    st().load(scene({ document: { grid, render: { A: {} } } }));
    expect(regionList(st().document)).toEqual(["A", "B"]);
  });

  it("regionColor is deterministic per letter", () => {
    expect(regionColor("A")).toBe(regionColor("A"));
    expect(regionColor("A")).not.toBe(regionColor("B"));
  });
});
