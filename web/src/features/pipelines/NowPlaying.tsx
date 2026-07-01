import { useEffect, useState } from "react";
import { Square, Radio } from "lucide-react";
import { Button, Badge, Spinner } from "@/components/ui/primitives";
import { toast } from "@/components/ui/toast";
import { errorMessage } from "@/api/errors";
import type { Pipeline } from "@/api/types";
import { useBoardRun, useStopBoard } from "@/features/boards/api";

const STATE_TONE: Record<string, "ok" | "warn" | "neutral"> = {
  running: "ok",
  paused: "warn",
  stopped: "neutral",
};

function describeEntry(pipeline: Pipeline, entryId: string | null): string {
  if (!entryId) return "—";
  const entry = pipeline.entries.find((e) => e.id === entryId);
  if (!entry) return "—";
  const label = entry.source_type === "job" ? `job: ${entry.job_name}` : `scene`;
  return `#${entry.position + 1} · ${label} · ${entry.duration_seconds}s`;
}

// Live "now playing" view: polls GET /boards/{id}/run every 2s and shows a
// countdown derived from the current entry's duration and the run's updated_at.
export function NowPlaying({ boardId, pipeline }: { boardId: string; pipeline: Pipeline }) {
  const { data: run, isLoading } = useBoardRun(boardId, 2000);
  const stop = useStopBoard();
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  if (isLoading) {
    return (
      <div className="flex justify-center py-4">
        <Spinner className="h-5 w-5" />
      </div>
    );
  }
  if (!run) {
    return <p className="text-sm text-neutral-500">No run assigned to this board yet.</p>;
  }

  const entry = pipeline.entries.find((e) => e.id === run.current_entry_id);
  const elapsed = (now - Date.parse(run.updated_at)) / 1000;
  const remaining = entry ? Math.max(0, Math.ceil(entry.duration_seconds - elapsed)) : 0;

  async function onStop() {
    try {
      await stop.mutateAsync(boardId);
      toast.success("Stopped");
    } catch (e) {
      toast.error(errorMessage(e, "Could not stop"));
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <span className="flex items-center gap-2 text-sm font-medium text-neutral-200">
          <Radio className="h-4 w-4 text-violet-400" /> Now playing
        </span>
        <Badge tone={STATE_TONE[run.state] ?? "neutral"}>{run.state}</Badge>
      </div>

      <div className="rounded-md border border-neutral-800 bg-neutral-900/50 p-3 text-sm">
        <div className="text-neutral-200">{describeEntry(pipeline, run.current_entry_id)}</div>
        {run.state === "running" && entry && (
          <div className="mt-1 text-xs text-neutral-500">~{remaining}s remaining on this entry</div>
        )}
      </div>

      <Button
        variant="danger"
        size="sm"
        onClick={onStop}
        disabled={stop.isPending || run.state === "stopped"}
        className="self-start"
      >
        <Square className="h-3.5 w-3.5" /> Stop
      </Button>
    </div>
  );
}
