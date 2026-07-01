import type { components } from "./schema";

// Friendly aliases for the generated OpenAPI component schemas.
export type User = components["schemas"]["UserOut"];
export type Scene = components["schemas"]["SceneOut"];
export type SceneIn = components["schemas"]["SceneIn"];
export type Board = components["schemas"]["BoardOut"];
export type BoardIn = components["schemas"]["BoardIn"];
export type Pipeline = components["schemas"]["PipelineOut"];
export type PipelineIn = components["schemas"]["PipelineIn"];
export type PipelineEntry = components["schemas"]["PipelineEntryOut"];
export type PipelineEntryIn = components["schemas"]["PipelineEntryIn"];
export type BoardRun = components["schemas"]["BoardRunOut"];
export type PreviewOut = components["schemas"]["PreviewOut"];

// The OpenAPI schema types `document` and `required_variables` loosely (dict/unknown).
// These interfaces capture the real shape the backend produces/consumes so the
// designer can edit them — the binding logic itself still lives server-side.

export type ColorSpec =
  | string
  | number
  | { data: string }
  | { rule: string; [param: string]: unknown };

export interface RenderRegion {
  bind?: string;
  as?: "text" | "glyphs" | "textbox" | "fill";
  color?: ColorSpec;
  align?: "left" | "center" | "right";
  transform?: string;
  fallback?: string;
  font?: string;
  [key: string]: unknown;
}

export interface SceneDocument {
  grid: string[];
  font?: string;
  render?: Record<string, RenderRegion>;
  labels?: Record<string, unknown>;
  [key: string]: unknown;
}

// One entry of SceneOut.required_variables (computed by the backend's scene_variables).
export interface RequiredVariable {
  name: string;
  kind?: "text" | "number" | "color" | "flag" | string;
  required?: boolean;
  fallback?: string | null;
}

export const JOB_NAMES = [
  "clock",
  "muni",
  "world_cup",
  "sport_highscores",
  "sport_lowscores",
  "spotify",
] as const;

export const BOARD_MODELS = ["flagship", "note"] as const;
