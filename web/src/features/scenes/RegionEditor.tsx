import { useSceneEditor } from "./store";
import type { RenderRegion } from "@/api/types";
import { Field, Input } from "@/components/ui/primitives";
import { Select } from "@/components/ui/select";
import { ColorPicker } from "./ColorPicker";

const AS_OPTIONS = [
  { value: "text", label: "text" },
  { value: "glyphs", label: "glyphs (big font)" },
  { value: "textbox", label: "textbox (wrapped)" },
  { value: "fill", label: "fill (solid color)" },
];
const ALIGN_OPTIONS = [
  { value: "left", label: "left" },
  { value: "center", label: "center" },
  { value: "right", label: "right" },
];
const TRANSFORM_OPTIONS = [
  { value: "", label: "none" },
  { value: "upper", label: "upper" },
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
        Select a region (a letter in the grid) to edit how it is filled.
      </p>
    );
  }

  const set = (field: keyof RenderRegion, value: unknown) =>
    !readOnly && setField(selected, field, value);

  return (
    <div className="flex flex-col gap-4">
      <div className="text-sm font-medium text-neutral-200">
        Region <span className="font-mono text-violet-300">{selected}</span>
      </div>

      <Field label="Bind (template variable)">
        <Input
          value={region.bind ?? ""}
          readOnly={readOnly}
          placeholder="e.g. message"
          onChange={(e) => set("bind", e.target.value)}
        />
      </Field>

      <Field label="Render as">
        <Select
          value={region.as ?? "text"}
          disabled={readOnly}
          options={AS_OPTIONS}
          onValueChange={(v) => set("as", v)}
        />
      </Field>

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

      <Field label="Color">
        <ColorPicker value={region.color} disabled={readOnly} onChange={(c) => set("color", c)} />
      </Field>

      <Field label="Fallback (used when the value is empty)">
        <Input
          value={region.fallback ?? ""}
          readOnly={readOnly}
          onChange={(e) => set("fallback", e.target.value)}
        />
      </Field>
    </div>
  );
}
