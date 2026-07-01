import type { RequiredVariable, SceneDocument } from "@/api/types";

// Live list of variables the sample-data form should expose while editing. Names
// come from the document's current binds + {data:key} color specs (so a freshly
// added bind gets a field immediately), enriched with kind/required/fallback
// metadata from the server-computed required_variables when it already knows them.
export function collectVariables(
  document: SceneDocument,
  serverVars: RequiredVariable[],
): RequiredVariable[] {
  const meta = new Map(serverVars.map((v) => [v.name, v]));
  const names = new Set<string>();
  const colorKeys = new Set<string>();

  const addColorData = (spec: unknown) => {
    if (spec && typeof spec === "object" && "data" in spec) {
      const key = (spec as { data: unknown }).data;
      if (typeof key === "string") {
        names.add(key);
        colorKeys.add(key);
      }
    }
  };

  for (const region of Object.values(document.render ?? {})) {
    if (region.bind) names.add(region.bind);
    addColorData(region.color);
    addColorData(region.fill); // glyph background color can also be {data:key}
  }
  // Keep any server-known variable even if the bind was just removed mid-edit.
  for (const v of serverVars) names.add(v.name);

  return [...names].map((name) => {
    if (meta.has(name)) return meta.get(name)!;
    // A key used as a {data:key} color must be an int code, so tag it as color
    // even before the server has recomputed required_variables.
    return colorKeys.has(name) ? { name, kind: "color" } : { name };
  });
}

// Sample data actually sent to /preview: the user's values, backfilled with sane
// defaults so the board renders instead of 422-ing on an empty required value.
// Color/number vars need a concrete value; text/flag can stay blank (renders empty).
export function seedSampleData(
  variables: RequiredVariable[],
  userSample: Record<string, unknown>,
): Record<string, unknown> {
  const out: Record<string, unknown> = {};
  for (const v of variables) {
    const userVal = userSample[v.name];
    if (userVal !== undefined && userVal !== "") {
      out[v.name] = userVal;
    } else if (v.fallback != null && v.fallback !== "") {
      out[v.name] = v.fallback;
    } else if (v.kind === "color") {
      out[v.name] = 69; // white chip
    } else if (v.kind === "number") {
      out[v.name] = 0;
    }
  }
  return out;
}
