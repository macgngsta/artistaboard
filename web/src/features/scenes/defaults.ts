import type { SceneDocument } from "@/api/types";

export const GRID_ROWS = 6;
export const GRID_COLS = 22;
export const FILLER = ".";

export function blankRow(): string {
  return FILLER.repeat(GRID_COLS);
}

// A minimal but illustrative starter: one full-width text region on row 3 bound to
// `message`, so a new scene renders something and surfaces one required variable.
export function newSceneDocument(): SceneDocument {
  const grid = Array.from({ length: GRID_ROWS }, () => blankRow());
  grid[2] = "A".repeat(GRID_COLS);
  return {
    grid,
    render: {
      A: { bind: "message", as: "text", align: "center", fallback: "HELLO" },
    },
  };
}
