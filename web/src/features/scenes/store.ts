import { create } from "zustand";
import type { RenderRegion, Scene, SceneDocument } from "@/api/types";
import { blankRow, GRID_COLS, GRID_ROWS } from "./defaults";

// Local editor state for the scene designer (Zustand per the plan). Holds the
// working document + sample_data that feed the debounced /preview call; the
// binding/render logic itself stays server-side.
interface SceneEditorState {
  loadedId: string | null;
  name: string;
  description: string;
  model: string;
  isSystem: boolean;
  document: SceneDocument;
  sampleData: Record<string, unknown>;
  selectedRegion: string | null;
  dirty: boolean;

  load: (scene: Scene) => void;
  setName: (name: string) => void;
  setRow: (index: number, value: string) => void;
  setFont: (font: string) => void;
  selectRegion: (region: string | null) => void;
  setRegionField: (region: string, field: keyof RenderRegion, value: unknown) => void;
  setSampleValue: (name: string, value: unknown) => void;
}

function normalizeRow(value: string): string {
  const upper = value.toUpperCase().slice(0, GRID_COLS);
  return upper.padEnd(GRID_COLS, ".");
}

function asDocument(raw: unknown): SceneDocument {
  // Accept the object form; coerce the bare-array form into { grid }.
  if (Array.isArray(raw)) {
    return { grid: raw.map((r) => (typeof r === "string" ? r : String(r))) };
  }
  const doc = (raw ?? {}) as SceneDocument;
  const grid = Array.isArray(doc.grid) ? doc.grid.slice(0, GRID_ROWS) : [];
  while (grid.length < GRID_ROWS) grid.push(blankRow());
  return { ...doc, grid, render: doc.render ?? {} };
}

export const useSceneEditor = create<SceneEditorState>((set) => ({
  loadedId: null,
  name: "",
  description: "",
  model: "flagship",
  isSystem: false,
  document: { grid: Array.from({ length: GRID_ROWS }, blankRow), render: {} },
  sampleData: {},
  selectedRegion: null,
  dirty: false,

  load: (scene) =>
    set({
      loadedId: scene.id,
      name: scene.name,
      description: scene.description,
      model: scene.model,
      isSystem: scene.is_system,
      document: asDocument(scene.document),
      sampleData: {},
      selectedRegion: null,
      dirty: false,
    }),

  setName: (name) => set({ name, dirty: true }),

  setRow: (index, value) =>
    set((s) => {
      const grid = [...s.document.grid];
      grid[index] = normalizeRow(value);
      return { document: { ...s.document, grid }, dirty: true };
    }),

  setFont: (font) => set((s) => ({ document: { ...s.document, font }, dirty: true })),

  selectRegion: (selectedRegion) => set({ selectedRegion }),

  setRegionField: (region, field, value) =>
    set((s) => {
      const render = { ...(s.document.render ?? {}) };
      const current: RenderRegion = { ...(render[region] ?? {}) };
      // Empty string clears optional fields so they aren't sent as "".
      if (value === "" || value === undefined || value === null) {
        delete current[field];
      } else {
        current[field] = value;
      }
      render[region] = current;
      return { document: { ...s.document, render }, dirty: true };
    }),

  setSampleValue: (name, value) =>
    set((s) => ({ sampleData: { ...s.sampleData, [name]: value } })),
}));

// Distinct region letters present in the grid, in reading order.
export function regionsInGrid(grid: string[]): string[] {
  const seen = new Set<string>();
  for (const row of grid) {
    for (const ch of row) {
      if (ch >= "A" && ch <= "Z") seen.add(ch);
    }
  }
  return [...seen].sort();
}
