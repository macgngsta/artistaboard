import type { Pipeline, PipelineEntryIn } from "@/api/types";

// Editor-local entry: string fields for form inputs + a stable key for dnd/react.
export interface WorkingEntry {
  key: string;
  source_type: "job" | "scene";
  job_name: string;
  scene_id: string;
  data_source: string;
  options: Record<string, unknown>; // per-job typed overrides; empty = inherit
  duration_seconds: number;
  refresh_seconds: string; // "" = none
}

function newKey(): string {
  return crypto.randomUUID();
}

export function emptyEntry(): WorkingEntry {
  return {
    key: newKey(),
    source_type: "job",
    job_name: "clock",
    scene_id: "",
    data_source: "",
    options: {},
    duration_seconds: 60,
    refresh_seconds: "",
  };
}

export function fromPipeline(pipeline: Pipeline): WorkingEntry[] {
  return pipeline.entries.map((e) => ({
    key: e.id,
    source_type: e.source_type === "scene" ? "scene" : "job",
    job_name: e.job_name ?? "",
    scene_id: e.scene_id ?? "",
    data_source: e.data_source ?? "",
    options: (e.options ?? {}) as Record<string, unknown>,
    duration_seconds: e.duration_seconds,
    refresh_seconds: e.refresh_seconds == null ? "" : String(e.refresh_seconds),
  }));
}

// Drop keys the user left unset so we send only real overrides (the backend
// treats an absent option as "inherit the global config default").
function prunedOptions(options: Record<string, unknown>): Record<string, unknown> | undefined {
  const entries = Object.entries(options).filter(
    ([, v]) => v !== "" && v !== undefined && v !== null,
  );
  return entries.length ? Object.fromEntries(entries) : undefined;
}

// Serialize to the API shape. Positions are implied by array order (the backend
// assigns 0-based positions from the order sent).
export function toEntryIn(e: WorkingEntry): PipelineEntryIn {
  const refresh = e.refresh_seconds.trim() === "" ? null : Number(e.refresh_seconds);
  if (e.source_type === "scene") {
    return {
      source_type: "scene",
      scene_id: e.scene_id,
      data_source: e.data_source || null,
      duration_seconds: e.duration_seconds,
      refresh_seconds: refresh,
    };
  }
  return {
    source_type: "job",
    job_name: e.job_name,
    options: prunedOptions(e.options),
    duration_seconds: e.duration_seconds,
    refresh_seconds: refresh,
  };
}
