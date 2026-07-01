import { useSceneEditor } from "./store";
import type { RequiredVariable } from "@/api/types";
import { Field, Input } from "@/components/ui/primitives";

// Feeds the live preview: one input per server-computed required variable. Values
// are sent as sample_data so bound regions render. `color`/`number` kinds accept a
// numeric code; text kinds accept a string.
export function SampleDataForm({ variables }: { variables: RequiredVariable[] }) {
  const sampleData = useSceneEditor((s) => s.sampleData);
  const setSampleValue = useSceneEditor((s) => s.setSampleValue);

  if (variables.length === 0) {
    return <p className="text-xs text-neutral-500">This scene has no bound variables.</p>;
  }

  return (
    <div className="flex flex-col gap-3">
      {variables.map((v) => {
        const numeric = v.kind === "color" || v.kind === "number";
        const raw = sampleData[v.name];
        return (
          <Field
            key={v.name}
            label={`${v.name}${v.required ? " *" : ""}${v.kind ? ` (${v.kind})` : ""}`}
          >
            <Input
              type={numeric ? "number" : "text"}
              value={raw === undefined || raw === null ? "" : String(raw)}
              placeholder={v.fallback ? `fallback: ${v.fallback}` : ""}
              onChange={(e) => {
                const val = e.target.value;
                setSampleValue(v.name, numeric ? (val === "" ? "" : Number(val)) : val);
              }}
            />
          </Field>
        );
      })}
    </div>
  );
}
