import { useSceneEditor, regionsInGrid } from "./store";
import { cn } from "@/lib/cn";
import { Field } from "@/components/ui/primitives";

// Left pane: edit document.grid as six 22-char rows. A letter A–Z marks a filler
// region; ".", " ", "#", "" are unassigned cells. Region chips below jump to the
// matching render config in the right pane.
export function GridEditor({ readOnly }: { readOnly: boolean }) {
  const grid = useSceneEditor((s) => s.document.grid);
  const setRow = useSceneEditor((s) => s.setRow);
  const selected = useSceneEditor((s) => s.selectedRegion);
  const selectRegion = useSceneEditor((s) => s.selectRegion);
  const regions = regionsInGrid(grid);

  return (
    <div className="flex flex-col gap-4">
      <Field label="Grid (6 rows × 22 cols · A–Z = region, . = blank)">
        <div className="flex flex-col gap-1">
          {grid.map((row, i) => (
            <input
              key={i}
              value={row}
              readOnly={readOnly}
              spellCheck={false}
              onChange={(e) => setRow(i, e.target.value)}
              className="w-full rounded border border-neutral-700 bg-neutral-900 px-2 py-1.5 font-mono text-sm tracking-[0.35em] text-neutral-100 focus:outline-none focus:ring-2 focus:ring-violet-600 read-only:opacity-70"
            />
          ))}
        </div>
      </Field>

      <div>
        <div className="mb-1.5 text-xs font-medium text-neutral-400">Regions</div>
        {regions.length === 0 ? (
          <p className="text-xs text-neutral-500">
            No regions yet. Type a letter (A–Z) into the grid to add one.
          </p>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {regions.map((r) => (
              <button
                key={r}
                onClick={() => selectRegion(r)}
                className={cn(
                  "flex h-8 w-8 items-center justify-center rounded font-mono text-sm",
                  selected === r
                    ? "bg-violet-600 text-white"
                    : "bg-neutral-800 text-neutral-200 hover:bg-neutral-700",
                )}
              >
                {r}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
