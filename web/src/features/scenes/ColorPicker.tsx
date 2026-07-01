import { COLOR_NAME_TO_CODE } from "@/lib/codes";
import type { ColorSpec } from "@/api/types";
import { Input } from "@/components/ui/primitives";
import { cn } from "@/lib/cn";
import { ColorSelect } from "./ColorSelect";

type Mode = "none" | "solid" | "data" | "rule";

function modeOf(color: ColorSpec | undefined): Mode {
  if (color === undefined) return "none";
  if (typeof color === "number" || typeof color === "string") return "solid";
  if ("data" in color) return "data";
  return "rule";
}

// Resolve a solid color spec (code or name) to its numeric chip code, or null.
function solidCode(color: ColorSpec | undefined): number | null {
  if (typeof color === "number") return color;
  if (typeof color === "string") return COLOR_NAME_TO_CODE[color.toLowerCase()] ?? null;
  return null;
}

// The variable name of a {data:key} color spec, or "".
function dataKey(color: ColorSpec | undefined): string {
  return color && typeof color === "object" && "data" in color && typeof color.data === "string"
    ? color.data
    : "";
}

const MODES: { key: Mode; label: string }[] = [
  { key: "none", label: "None" },
  { key: "solid", label: "Solid" },
  { key: "data", label: "From data" },
];

// Graphical color control for a region: pick a solid chip, bind to a data key, or
// leave unset (defaults to white on the board). {rule:...} specs (leader/imminent)
// from system scenes are shown read-only with a clear action.
export function ColorPicker({
  value,
  onChange,
  disabled,
}: {
  value: ColorSpec | undefined;
  onChange: (color: ColorSpec | undefined) => void;
  disabled?: boolean;
}) {
  const mode = modeOf(value);

  return (
    <div className="flex flex-col gap-2">
      {mode === "rule" ? (
        <div className="flex items-center justify-between rounded-md border border-neutral-800 bg-neutral-900/50 px-3 py-2 text-xs text-neutral-400">
          <span>advanced rule: {(value as { rule: string }).rule}</span>
          <button
            className="text-neutral-500 hover:text-neutral-200"
            disabled={disabled}
            onClick={() => onChange(undefined)}
          >
            clear
          </button>
        </div>
      ) : (
        <>
          <div className="inline-flex rounded-md border border-neutral-800 p-0.5 text-xs">
            {MODES.map((m) => (
              <button
                key={m.key}
                disabled={disabled}
                onClick={() => {
                  if (m.key === "none") onChange(undefined);
                  else if (m.key === "solid") onChange(solidCode(value) ?? 69);
                  else onChange({ data: dataKey(value) });
                }}
                className={cn(
                  "flex-1 rounded px-2 py-1 transition-colors",
                  mode === m.key ? "bg-neutral-800 text-neutral-100" : "text-neutral-400",
                )}
              >
                {m.label}
              </button>
            ))}
          </div>

          {mode === "solid" && (
            <ColorSelect
              value={solidCode(value) ?? undefined}
              disabled={disabled}
              onChange={(code) => onChange(code)}
            />
          )}

          {mode === "data" && (
            <Input
              value={dataKey(value)}
              disabled={disabled}
              placeholder="variable name, e.g. time_color"
              onChange={(e) => onChange({ data: e.target.value })}
            />
          )}
        </>
      )}
    </div>
  );
}
