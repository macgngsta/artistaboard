import { useSortable } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, Trash2 } from "lucide-react";
import { Input } from "@/components/ui/primitives";
import { Select } from "@/components/ui/select";
import { JOB_NAMES, type Scene } from "@/api/types";
import type { WorkingEntry } from "./entry";

const SOURCE_OPTIONS = [
  { value: "job", label: "job" },
  { value: "scene", label: "scene" },
];
const JOB_OPTIONS = JOB_NAMES.map((j) => ({ value: j, label: j }));
const DATA_SOURCE_OPTIONS = [{ value: "", label: "none" }, ...JOB_OPTIONS];

export function PipelineEntryRow({
  entry,
  scenes,
  onChange,
  onRemove,
}: {
  entry: WorkingEntry;
  scenes: Scene[];
  onChange: (patch: Partial<WorkingEntry>) => void;
  onRemove: () => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: entry.key,
  });
  const sceneOptions = scenes.map((s) => ({ value: s.id, label: s.name }));

  return (
    <div
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`flex items-end gap-2 rounded-md border border-neutral-800 bg-neutral-900/50 p-3 ${
        isDragging ? "opacity-60" : ""
      }`}
    >
      <button
        className="mb-2 cursor-grab text-neutral-500 hover:text-neutral-300"
        {...attributes}
        {...listeners}
        aria-label="Drag to reorder"
      >
        <GripVertical className="h-4 w-4" />
      </button>

      <div className="grid flex-1 grid-cols-2 gap-2 md:grid-cols-4">
        <Labeled label="Source">
          <Select
            value={entry.source_type}
            options={SOURCE_OPTIONS}
            onValueChange={(v) => onChange({ source_type: v as WorkingEntry["source_type"] })}
          />
        </Labeled>

        {entry.source_type === "job" ? (
          <Labeled label="Job">
            <Select
              value={entry.job_name || "clock"}
              options={JOB_OPTIONS}
              onValueChange={(v) => onChange({ job_name: v })}
            />
          </Labeled>
        ) : (
          <>
            <Labeled label="Scene">
              <Select
                value={entry.scene_id}
                options={sceneOptions}
                placeholder="Pick a scene"
                onValueChange={(v) => onChange({ scene_id: v })}
              />
            </Labeled>
            <Labeled label="Data source">
              <Select
                value={entry.data_source}
                options={DATA_SOURCE_OPTIONS}
                placeholder="none"
                onValueChange={(v) => onChange({ data_source: v })}
              />
            </Labeled>
          </>
        )}

        <Labeled label="Duration (s)">
          <Input
            type="number"
            min={1}
            value={entry.duration_seconds}
            onChange={(e) => onChange({ duration_seconds: Number(e.target.value) })}
          />
        </Labeled>

        <Labeled label="Refresh (s, optional)">
          <Input
            type="number"
            min={1}
            value={entry.refresh_seconds}
            onChange={(e) => onChange({ refresh_seconds: e.target.value })}
          />
        </Labeled>
      </div>

      <button
        onClick={onRemove}
        className="mb-2 text-neutral-500 hover:text-red-400"
        aria-label="Remove entry"
      >
        <Trash2 className="h-4 w-4" />
      </button>
    </div>
  );
}

function Labeled({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wide text-neutral-500">{label}</span>
      {children}
    </div>
  );
}
