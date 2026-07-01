import type { DataSource } from "@/api/types";

// Human "polled 2m ago" / "just now" / "never" from a source's age. The backend
// computes age_seconds at fetch time; the query refetches on an interval so it ages.
export function formatAge(source: Pick<DataSource, "age_seconds" | "has_data">): string {
  if (!source.has_data || source.age_seconds == null) return "never polled";
  const s = source.age_seconds;
  if (s < 5) return "just now";
  if (s < 60) return `${Math.floor(s)}s ago`;
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

// A series is stale if it has never been polled or its newest snapshot is over an hour
// old — the UI tints these to flag boards painting from a live fetch fallback.
export function isStale(source: Pick<DataSource, "age_seconds" | "has_data">): boolean {
  return !source.has_data || source.age_seconds == null || source.age_seconds >= 3600;
}
