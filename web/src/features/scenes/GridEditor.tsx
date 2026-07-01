import { useEffect, useState } from "react";
import { Eraser, Plus, X } from "lucide-react";
import { useSceneEditor, regionList, regionColor } from "./store";
import { cn } from "@/lib/cn";

// Left pane: a graphical 6×22 painter. Pick a region (or the eraser) from the
// palette, then click/drag across cells to paint them into that region. Regions
// are just letters A–Z in document.grid; blanks are fillers ("."). Add/remove
// regions from the palette. The render config for the selected region lives in the
// right pane (selecting a region here also targets it there).
export function GridEditor({ readOnly }: { readOnly: boolean }) {
  const grid = useSceneEditor((s) => s.document.grid);
  const document = useSceneEditor((s) => s.document);
  const selected = useSceneEditor((s) => s.selectedRegion);
  const eraseMode = useSceneEditor((s) => s.eraseMode);
  const setCell = useSceneEditor((s) => s.setCell);
  const selectRegion = useSceneEditor((s) => s.selectRegion);
  const setEraseMode = useSceneEditor((s) => s.setEraseMode);
  const addRegion = useSceneEditor((s) => s.addRegion);
  const removeRegion = useSceneEditor((s) => s.removeRegion);

  const regions = regionList(document);
  const [painting, setPainting] = useState(false);

  // Painting continues while the pointer is held down, even across cells; release
  // anywhere ends the stroke.
  useEffect(() => {
    const up = () => setPainting(false);
    window.addEventListener("pointerup", up);
    return () => window.removeEventListener("pointerup", up);
  }, []);

  const cols = grid[0]?.length ?? 22;

  return (
    <div className="flex flex-col gap-4">
      {/* Palette */}
      <div>
        <div className="mb-1.5 text-xs font-medium text-neutral-400">
          Regions — pick one, then paint on the grid
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          {regions.map((r) => (
            <div key={r} className="group relative">
              <button
                onClick={() => selectRegion(r)}
                disabled={readOnly}
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded font-mono text-sm font-semibold text-black",
                  selected === r && !eraseMode
                    ? "ring-2 ring-white ring-offset-2 ring-offset-neutral-900"
                    : "opacity-80 hover:opacity-100",
                )}
                style={{ backgroundColor: regionColor(r) }}
              >
                {r}
              </button>
              {!readOnly && (
                <button
                  onClick={() => removeRegion(r)}
                  aria-label={`Remove region ${r}`}
                  className="absolute -right-1 -top-1 hidden h-4 w-4 items-center justify-center rounded-full bg-neutral-950 text-neutral-400 ring-1 ring-neutral-700 hover:text-red-400 group-hover:flex"
                >
                  <X className="h-2.5 w-2.5" />
                </button>
              )}
            </div>
          ))}

          <button
            onClick={addRegion}
            disabled={readOnly}
            className="flex h-8 items-center gap-1 rounded border border-dashed border-neutral-700 px-2 text-xs text-neutral-300 hover:bg-neutral-800 disabled:opacity-50"
          >
            <Plus className="h-3.5 w-3.5" /> Add
          </button>

          <button
            onClick={() => setEraseMode(!eraseMode)}
            disabled={readOnly}
            className={cn(
              "flex h-8 items-center gap-1 rounded border px-2 text-xs disabled:opacity-50",
              eraseMode
                ? "border-white bg-neutral-200 text-black"
                : "border-neutral-700 text-neutral-300 hover:bg-neutral-800",
            )}
          >
            <Eraser className="h-3.5 w-3.5" /> Erase
          </button>
        </div>
      </div>

      {/* Painter grid */}
      <div
        className="inline-grid touch-none select-none gap-[2px] rounded-lg bg-black p-2"
        style={{ gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))` }}
      >
        {grid.flatMap((row, r) =>
          row.split("").map((ch, c) => {
            const isRegion = ch >= "A" && ch <= "Z";
            return (
              <div
                key={`${r}-${c}`}
                onPointerDown={(e) => {
                  if (readOnly) return;
                  e.preventDefault();
                  setPainting(true);
                  setCell(r, c);
                }}
                onPointerEnter={() => {
                  if (!readOnly && painting) setCell(r, c);
                }}
                className={cn(
                  "flex aspect-[3/4] items-center justify-center rounded-[2px] font-mono text-[10px] font-semibold",
                  isRegion ? "text-black" : "bg-[#141414] text-neutral-700",
                  readOnly ? "cursor-default" : "cursor-pointer",
                )}
                style={isRegion ? { backgroundColor: regionColor(ch) } : undefined}
              >
                {isRegion ? ch : ""}
              </div>
            );
          }),
        )}
      </div>

      <p className="text-xs text-neutral-500">
        {eraseMode
          ? "Erasing — click or drag to clear cells."
          : selected
            ? `Painting region ${selected} — click or drag on the grid.`
            : "Select a region above (or Add one) to start painting."}
      </p>
    </div>
  );
}
