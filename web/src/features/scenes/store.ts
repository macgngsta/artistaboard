import { create } from "zustand";
import type { RenderRegion, Scene, SceneDocument } from "@/api/types";
import { blankRow, FILLER, GRID_COLS, GRID_ROWS } from "./defaults";

const ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ".split("");

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
  eraseMode: boolean;
  dirty: boolean;

  load: (scene: Scene) => void;
  setName: (name: string) => void;
  setRow: (index: number, value: string) => void;
  setCell: (row: number, col: number) => void;
  setEraseMode: (erase: boolean) => void;
  addRegion: () => void;
  removeRegion: (region: string) => void;
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
  eraseMode: false,
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
      eraseMode: false,
      dirty: false,
    }),

  setName: (name) => set({ name, dirty: true }),

  setRow: (index, value) =>
    set((s) => {
      const grid = [...s.document.grid];
      grid[index] = normalizeRow(value);
      return { document: { ...s.document, grid }, dirty: true };
    }),

  // Paint one cell with the current brush: the selected region letter, or a blank
  // filler when erasing. This is how the graphical grid mutates document.grid.
  setCell: (row, col) =>
    set((s) => {
      if (s.isSystem) return s;
      const paint = s.eraseMode ? FILLER : s.selectedRegion;
      if (!paint) return s; // no brush selected and not erasing
      const grid = [...s.document.grid];
      const chars = grid[row].split("");
      if (chars[col] === paint) return s;
      chars[col] = paint;
      grid[row] = chars.join("");
      return { document: { ...s.document, grid }, dirty: true };
    }),

  setEraseMode: (eraseMode) => set({ eraseMode }),

  // Create the next free region letter (A–Z) and select it as the brush. It has no
  // cells yet — the user paints them — but it shows in the palette immediately
  // because it now exists in render config.
  addRegion: () =>
    set((s) => {
      const used = new Set(regionList(s.document));
      const next = ALPHABET.find((c) => !used.has(c));
      if (!next) return s; // all 26 letters in use
      const render = { ...(s.document.render ?? {}), [next]: {} };
      return {
        document: { ...s.document, render },
        selectedRegion: next,
        eraseMode: false,
        dirty: true,
      };
    }),

  // Remove a region entirely: clear its painted cells and drop its render config.
  removeRegion: (region) =>
    set((s) => {
      const grid = s.document.grid.map((row) =>
        row
          .split("")
          .map((c) => (c === region ? FILLER : c))
          .join(""),
      );
      const render = { ...(s.document.render ?? {}) };
      delete render[region];
      return {
        document: { ...s.document, grid, render },
        selectedRegion: s.selectedRegion === region ? null : s.selectedRegion,
        dirty: true,
      };
    }),

  setFont: (font) => set((s) => ({ document: { ...s.document, font }, dirty: true })),

  selectRegion: (selectedRegion) => set({ selectedRegion, eraseMode: false }),

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

// All regions that "exist": painted in the grid OR configured in render (so a
// freshly added, not-yet-painted region still shows in the palette).
export function regionList(document: SceneDocument): string[] {
  const seen = new Set<string>(regionsInGrid(document.grid));
  for (const key of Object.keys(document.render ?? {})) {
    if (key >= "A" && key <= "Z") seen.add(key);
  }
  return [...seen].sort();
}

// Stable, visually distinct fill color per region letter for the painter overlay.
const REGION_HUES = [265, 190, 145, 25, 330, 90, 210, 45, 300, 165, 0, 240];
export function regionColor(region: string): string {
  const idx = region.charCodeAt(0) - 65;
  return `hsl(${REGION_HUES[idx % REGION_HUES.length]} 70% 55%)`;
}
