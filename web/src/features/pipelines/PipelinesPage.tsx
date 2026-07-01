import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Repeat, ArrowRight, Trash2 } from "lucide-react";
import { PageHeader } from "@/components/AppLayout";
import { Button, Card, Badge, Spinner } from "@/components/ui/primitives";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/api/errors";
import type { Pipeline } from "@/api/types";
import { usePipelines, useCreatePipeline, useDeletePipeline } from "./api";

export function PipelinesPage() {
  const navigate = useNavigate();
  const { data: pipelines, isLoading } = usePipelines();
  const createPipeline = useCreatePipeline();
  const deletePipeline = useDeletePipeline();
  const [busyId, setBusyId] = useState<string | null>(null);

  async function create() {
    try {
      const p = await createPipeline.mutateAsync({ name: "Untitled pipeline", loop: true, entries: [] });
      navigate(`/pipelines/${p.id}`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not create pipeline");
    }
  }

  async function remove(p: Pipeline) {
    if (!confirm(`Delete pipeline “${p.name}”?`)) return;
    setBusyId(p.id);
    try {
      await deletePipeline.mutateAsync(p.id);
      toast.success("Pipeline deleted");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not delete pipeline");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <PageHeader title="Pipelines">
        <Button onClick={create} disabled={createPipeline.isPending}>
          <Plus className="h-4 w-4" /> New pipeline
        </Button>
      </PageHeader>

      <div className="p-6">
        {isLoading ? (
          <div className="flex justify-center py-16">
            <Spinner className="h-6 w-6" />
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {pipelines?.map((p) => (
              <Card key={p.id} className="flex flex-col gap-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate font-medium text-neutral-100">{p.name}</div>
                    <div className="mt-0.5 text-xs text-neutral-500">
                      {p.entries.length} {p.entries.length === 1 ? "entry" : "entries"}
                    </div>
                  </div>
                  {p.loop && (
                    <Badge tone="info" className="shrink-0">
                      <Repeat className="mr-1 h-3 w-3" /> Loop
                    </Badge>
                  )}
                </div>
                <div className="mt-auto flex items-center gap-2">
                  <Button size="sm" onClick={() => navigate(`/pipelines/${p.id}`)}>
                    Edit <ArrowRight className="h-3.5 w-3.5" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-red-400"
                    onClick={() => remove(p)}
                    disabled={busyId === p.id}
                  >
                    <Trash2 className="h-3.5 w-3.5" />
                  </Button>
                </div>
              </Card>
            ))}
            {pipelines?.length === 0 && (
              <p className="text-sm text-neutral-500">No pipelines yet. Create one to sequence scenes and jobs.</p>
            )}
          </div>
        )}
      </div>
    </>
  );
}
