import { charForCode, colorForCode, isColorCode } from "@/lib/codes";
import { cn } from "@/lib/cn";

// Renders the /preview endpoint's `characters: number[][]` as a split-flap board.
// This is display-only — it never interprets bindings; it just maps each code to
// a glyph or a color chip using the backend-mirrored code table.
export function BoardGrid({
  characters,
  className,
}: {
  characters: number[][];
  className?: string;
}) {
  return (
    <div
      className={cn(
        "inline-grid gap-[3px] rounded-lg bg-black p-2 shadow-inner",
        className,
      )}
      style={{ gridTemplateColumns: `repeat(${characters[0]?.length ?? 22}, minmax(0, 1fr))` }}
    >
      {characters.flatMap((row, r) =>
        row.map((code, c) => <Tile key={`${r}-${c}`} code={code} />),
      )}
    </div>
  );
}

function Tile({ code }: { code: number }) {
  const chip = isColorCode(code) ? colorForCode(code) : null;
  return (
    <div
      // Fixed dark colors: the board depicts a physical black Vestaboard in both themes.
      className="relative flex aspect-[3/4] items-center justify-center rounded-[3px] bg-[#141414] font-mono text-[clamp(8px,1.6vw,20px)] font-semibold uppercase leading-none text-[#e5e5e7] select-none"
      style={chip ? { backgroundColor: chip } : undefined}
      // A thin hinge line down the middle evokes the physical split-flap tile.
    >
      <span className="pointer-events-none absolute inset-x-0 top-1/2 h-px -translate-y-px bg-black/40" />
      {!chip && <span>{charForCode(code)}</span>}
    </div>
  );
}
