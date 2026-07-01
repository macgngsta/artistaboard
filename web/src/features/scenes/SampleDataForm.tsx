import { useSceneEditor } from "./store";
import type { RequiredVariable } from "@/api/types";
import { Field, Input } from "@/components/ui/primitives";
import { ColorSelect } from "./ColorSelect";
import { variableRegions } from "./variables";

// Feeds the live preview: one control per server-computed required variable.
// Editing any field auto-repaints the preview (debounced). Color variables use a
// named color dropdown; numbers use a number input; everything else is text.
export function SampleDataForm({ variables }: { variables: RequiredVariable[] }) {
  const sampleData = useSceneEditor((s) => s.sampleData);
  const setSampleValue = useSceneEditor((s) => s.setSampleValue);
  const document = useSceneEditor((s) => s.document);
  const regionsByVar = variableRegions(document);

  if (variables.length === 0) {
    return <p className="text-xs text-neutral-500">This scene has no bound variables.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      {variables.map((v) => {
        const raw = sampleData[v.name];
        const regions = regionsByVar[v.name] ?? [];
        const label = `${v.name}${v.required ? " *" : ""}${v.kind ? ` (${v.kind})` : ""}`;
        return (
          <Field
            key={v.name}
            label={
              regions.length ? `${label} · region ${regions.join(", ")}` : label
            }
          >
            {v.kind === "color" ? (
              <ColorSelect
                value={raw === undefined || raw === null || raw === "" ? undefined : Number(raw)}
                onChange={(code) => setSampleValue(v.name, code)}
              />
            ) : (
              <Input
                type={v.kind === "number" ? "number" : "text"}
                value={raw === undefined || raw === null ? "" : String(raw)}
                placeholder={v.fallback ? `fallback: ${v.fallback}` : ""}
                onChange={(e) => {
                  const val = e.target.value;
                  setSampleValue(v.name, v.kind === "number" ? (val === "" ? "" : Number(val)) : val);
                }}
              />
            )}
          </Field>
        );
      })}
    </div>
  );
}
