import * as SelectPrimitive from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import { regionColor } from "./store";

function Badge({ region }: { region: string }) {
  return (
    <span
      className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded font-mono text-xs font-semibold text-black"
      style={{ backgroundColor: regionColor(region) }}
    >
      {region}
    </span>
  );
}

// Switch which region the right-hand editor targets, without hunting for its small
// colored badge on the grid palette. Value is the region letter.
export function RegionSelect({
  value,
  regions,
  onChange,
  disabled,
  placeholder = "Select a region",
}: {
  value: string;
  regions: string[];
  onChange: (region: string) => void;
  disabled?: boolean;
  placeholder?: string;
}) {
  return (
    <SelectPrimitive.Root value={value || undefined} onValueChange={onChange} disabled={disabled}>
      <SelectPrimitive.Trigger className="inline-flex h-9 w-full items-center justify-between rounded-md border border-neutral-700 bg-neutral-900 px-2.5 text-sm text-neutral-100 focus:outline-none focus:ring-2 focus:ring-violet-600 disabled:opacity-50">
        <span className="flex items-center gap-2">
          {value ? (
            <>
              <Badge region={value} />
              Region {value}
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
            {regions.map((r) => (
              <SelectPrimitive.Item
                key={r}
                value={r}
                className="relative flex cursor-pointer select-none items-center gap-2 rounded py-1.5 pl-7 pr-3 outline-none data-[highlighted]:bg-neutral-800"
              >
                <SelectPrimitive.ItemIndicator className="absolute left-2">
                  <Check className="h-3.5 w-3.5" />
                </SelectPrimitive.ItemIndicator>
                <Badge region={r} />
                <SelectPrimitive.ItemText>Region {r}</SelectPrimitive.ItemText>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}
