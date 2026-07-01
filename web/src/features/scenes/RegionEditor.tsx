import { useSceneEditor } from "./store";
import type { RenderRegion } from "@/api/types";
import { Field, Input } from "@/components/ui/primitives";
import { Select } from "@/components/ui/select";
import { ColorPicker } from "./ColorPicker";
import { cn } from "@/lib/cn";

// Region-type presets map the four backend render modes to plain-language choices,
// so you pick "what goes here" instead of guessing the `as` value.
const PRESETS = [
  { as: "text", label: "Text", hint: "One character per cell, on a single line." },
  { as: "glyphs", label: "Big number", hint: "Large multi-cell font — great for a clock or score." },
  { as: "textbox", label: "Wrapped text", hint: "Long text wrapped across the region's rows." },
  { as: "fill", label: "Solid color", hint: "Paint the whole region one color — no text." },
] as const;

const ALIGN_OPTIONS = [
  { value: "left", label: "left" },
  { value: "center", label: "center" },
  { value: "right", label: "right" },
];
const TRANSFORM_OPTIONS = [
  { value: "", label: "none" },
  { value: "upper", label: "UPPERCASE" },
];

export function RegionEditor({ readOnly }: { readOnly: boolean }) {
  const selected = useSceneEditor((s) => s.selectedRegion);
  const region = useSceneEditor((s) =>
    s.selectedRegion ? (s.document.render?.[s.selectedRegion] ?? {}) : null,
  );
  const setField = useSceneEditor((s) => s.setRegionField);

  if (!selected || !region) {
    return (
      <p className="text-sm text-neutral-500">
        Select a region (a letter in the grid) to choose what it shows.
      </p>
    );
  }

  const set = (field: keyof RenderRegion, value: unknown) =>
    !readOnly && setField(selected, field, value);

  const as = (region.as as string) ?? "text";
  const activePreset = PRESETS.find((p) => p.as === as) ?? PRESETS[0];
  const isFill = as === "fill";

  return (
    <div className="flex flex-col gap-4">
      <div className="text-sm font-medium text-neutral-200">
        Region <span className="font-mono text-violet-300">{selected}</span>
      </div>

      {/* What goes in this region */}
      <Field label="What goes here?">
        <div className="grid grid-cols-2 gap-1.5">
          {PRESETS.map((p) => (
            <button
              key={p.as}
              disabled={readOnly}
              onClick={() => set("as", p.as)}
              className={cn(
                "rounded-md border px-2 py-1.5 text-left text-sm transition-colors disabled:opacity-50",
                as === p.as
                  ? "border-violet-500 bg-violet-600/20 text-neutral-100"
                  : "border-neutral-700 text-neutral-300 hover:bg-neutral-800",
              )}
            >
              {p.label}
            </button>
          ))}
        </div>
        <p className="mt-1.5 text-xs text-neutral-500">{activePreset.hint}</p>
      </Field>

      {!isFill && (
        <Field label="Data">
          <Input
            value={region.bind ?? ""}
            readOnly={readOnly}
            placeholder="e.g. time, message, arrival1"
            onChange={(e) => set("bind", e.target.value)}
          />
          <p className="mt-1.5 text-xs text-neutral-500">
            The variable that fills this region. Give it a value under Sample data below — on a
            board, a job's data source supplies it.
          </p>
        </Field>
      )}

      {!isFill && (
        <div className="grid grid-cols-2 gap-3">
          <Field label="Align">
            <Select
              value={region.align ?? "left"}
              disabled={readOnly}
              options={ALIGN_OPTIONS}
              onValueChange={(v) => set("align", v)}
            />
          </Field>
          <Field label="Transform">
            <Select
              value={region.transform ?? ""}
              disabled={readOnly}
              options={TRANSFORM_OPTIONS}
              onValueChange={(v) => set("transform", v)}
            />
          </Field>
        </div>
      )}

      <Field label={isFill ? "Fill color" : "Text color"}>
        <ColorPicker value={region.color} disabled={readOnly} onChange={(c) => set("color", c)} />
      </Field>

      {!isFill && (
        <Field label="Fallback">
          <Input
            value={region.fallback ?? ""}
            readOnly={readOnly}
            placeholder="shown when the value is empty"
            onChange={(e) => set("fallback", e.target.value)}
          />
        </Field>
      )}
    </div>
  );
}
