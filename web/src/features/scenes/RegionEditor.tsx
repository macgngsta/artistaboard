import { useSceneEditor } from "./store";
import type { ColorSpec, RenderRegion } from "@/api/types";
import { Field, Input } from "@/components/ui/primitives";
import { Select } from "@/components/ui/select";

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

// Serialize a color spec back into the text field. Names/codes show raw;
// {data} / {rule} objects show as JSON for advanced editing.
function colorToText(color: ColorSpec | undefined): string {
  if (color === undefined) return "";
  if (typeof color === "string" || typeof color === "number") return String(color);
  return JSON.stringify(color);
}

// Parse the text field into the shape the backend expects: a number code, a
// color name, or a {data}/{rule} object. Empty clears the field.
function textToColor(text: string): ColorSpec | undefined {
  const t = text.trim();
  if (!t) return undefined;
  if (t.startsWith("{")) {
    try {
      return JSON.parse(t) as ColorSpec;
    } catch {
      return t; // leave as-is; the server 422 will explain if invalid
    }
  }
  return /^\d+$/.test(t) ? Number(t) : t;
}

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

      <Field label='Color (name "violet", code 68, or {"data":"key"})'>
        <Input
          value={colorToText(region.color)}
          readOnly={readOnly}
          placeholder="white"
          onChange={(e) => set("color", textToColor(e.target.value))}
        />
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
