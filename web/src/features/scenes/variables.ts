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

  for (const region of Object.values(document.render ?? {})) {
    if (region.bind) names.add(region.bind);
    const color = region.color;
    if (color && typeof color === "object" && "data" in color && typeof color.data === "string") {
      names.add(color.data);
    }
  }
  // Keep any server-known variable even if the bind was just removed mid-edit.
  for (const v of serverVars) names.add(v.name);

  return [...names].map((name) => meta.get(name) ?? { name });
}
