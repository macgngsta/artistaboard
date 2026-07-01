import { useQuery } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";

export interface JobOptionField {
  name: string;
  title: string;
  kind: "string" | "integer" | "boolean";
}

// Catalogue of built-in jobs and the JSON Schema of their typed options, so the
// pipeline editor can render a per-entry options form that matches the backend's
// validation (registry.options_overrides). Options are cheap and static.
export function useJobs() {
  return useQuery({
    queryKey: ["jobs"],
    staleTime: 5 * 60_000,
    queryFn: async () => unwrap(await api.GET("/jobs")),
  });
}

// Each option is a Pydantic Optional[...] field: anyOf [<type>, null], default null.
// Pull the concrete non-null type so we can pick the right input control.
export function optionFields(optionsSchema: Record<string, unknown>): JobOptionField[] {
  const props = (optionsSchema?.properties ?? {}) as Record<string, Record<string, unknown>>;
  return Object.entries(props).map(([name, spec]) => {
    const anyOf = (spec.anyOf as { type?: string }[] | undefined) ?? [];
    const type = (spec.type as string | undefined) ?? anyOf.find((t) => t.type && t.type !== "null")?.type;
    const kind: JobOptionField["kind"] =
      type === "integer" || type === "number" ? "integer" : type === "boolean" ? "boolean" : "string";
    return { name, title: (spec.title as string) ?? name, kind };
  });
}
