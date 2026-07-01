import * as SelectPrimitive from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import { COLOR_CODES } from "@/lib/codes";
import { cn } from "@/lib/cn";

const COLORS = Object.entries(COLOR_CODES).map(([code, c]) => ({
  code: Number(code),
  name: c.name,
  hex: c.hex,
}));

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

function Swatch({ hex }: { hex: string }) {
  return (
    <span
      className="inline-block h-3.5 w-3.5 shrink-0 rounded-sm border border-neutral-600"
      style={{ backgroundColor: hex }}
    />
  );
}

// A color chosen by name: the dropdown shows a swatch + word (Red, Blue, Green…)
// and stores the numeric board code. Used for solid region colors and for
// color-typed sample-data variables so nobody has to know that 65 means yellow.
export function ColorSelect({
  value,
  onChange,
  disabled,
  placeholder = "Pick a color",
}: {
  value: number | undefined;
  onChange: (code: number) => void;
  disabled?: boolean;
  placeholder?: string;
}) {
  const current = value != null ? COLOR_CODES[value] : undefined;
  return (
    <SelectPrimitive.Root
      value={value != null ? String(value) : undefined}
      onValueChange={(v) => onChange(Number(v))}
      disabled={disabled}
    >
      <SelectPrimitive.Trigger
        className={cn(
          "inline-flex h-9 w-full items-center justify-between rounded-md border border-neutral-700 bg-neutral-900 px-3 text-sm text-neutral-100 focus:outline-none focus:ring-2 focus:ring-violet-600 disabled:opacity-50",
        )}
      >
        <span className="flex items-center gap-2">
          {current ? (
            <>
              <Swatch hex={current.hex} />
              {cap(current.name)}
            </>
          ) : (
            <span className="text-neutral-500">{placeholder}</span>
          )}
        </span>
        <ChevronDown className="h-4 w-4 opacity-60" />
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          position="popper"
          sideOffset={4}
          className="z-50 max-h-72 overflow-hidden rounded-md border border-neutral-700 bg-neutral-900 text-sm text-neutral-100 shadow-xl"
        >
          <SelectPrimitive.Viewport className="p-1">
            {COLORS.map((c) => (
              <SelectPrimitive.Item
                key={c.code}
                value={String(c.code)}
                className="relative flex cursor-pointer select-none items-center gap-2 rounded py-1.5 pl-7 pr-3 outline-none data-[highlighted]:bg-neutral-800"
              >
                <SelectPrimitive.ItemIndicator className="absolute left-2">
                  <Check className="h-3.5 w-3.5" />
                </SelectPrimitive.ItemIndicator>
                <Swatch hex={c.hex} />
                <SelectPrimitive.ItemText>{cap(c.name)}</SelectPrimitive.ItemText>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}
