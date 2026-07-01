import { Input } from "@/components/ui/primitives";
import { Select } from "@/components/ui/select";
import { optionFields, type JobOptionField } from "./jobs";

const BOOL_OPTIONS = [
  { value: "", label: "inherit" },
  { value: "true", label: "on" },
  { value: "false", label: "off" },
];

// Renders one control per typed job option. An empty/"inherit" value is omitted on
// save so the backend falls back to the global config default for that option.
export function JobOptionsFields({
  optionsSchema,
  options,
  onChange,
}: {
  optionsSchema: Record<string, unknown>;
  options: Record<string, unknown>;
  onChange: (options: Record<string, unknown>) => void;
}) {
  const fields = optionFields(optionsSchema);
  if (fields.length === 0) {
    return <p className="text-xs text-neutral-500">This job has no options.</p>;
  }

  function set(name: string, value: unknown) {
    const next = { ...options };
    if (value === "" || value === undefined) delete next[name];
    else next[name] = value;
    onChange(next);
  }

  return (
    <div className="grid grid-cols-2 gap-2">
      {fields.map((f) => (
        <Control key={f.name} field={f} value={options[f.name]} onSet={(v) => set(f.name, v)} />
      ))}
    </div>
  );
}

function Control({
  field,
  value,
  onSet,
}: {
  field: JobOptionField;
  value: unknown;
  onSet: (value: unknown) => void;
}) {
  const raw = value === undefined || value === null ? "" : String(value);
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <span className="text-[10px] uppercase tracking-wide text-neutral-500">{field.title}</span>
      {field.kind === "boolean" ? (
        <Select
          value={raw}
          options={BOOL_OPTIONS}
          placeholder="inherit"
          onValueChange={(v) => onSet(v === "" ? "" : v === "true")}
        />
      ) : (
        <Input
          type={field.kind === "integer" ? "number" : "text"}
          value={raw}
          placeholder="inherit"
          onChange={(e) => {
            const v = e.target.value;
            onSet(field.kind === "integer" ? (v === "" ? "" : Number(v)) : v);
          }}
        />
      )}
    </div>
  );
}
