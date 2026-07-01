import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Copy, Trash2, Lock } from "lucide-react";
import { PageHeader } from "@/components/AppLayout";
import { Button, Card, Badge, Spinner } from "@/components/ui/primitives";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/api/errors";
import type { Scene, SceneDocument } from "@/api/types";
import { useScenes, useCreateScene, useDeleteScene } from "./api";
import { newSceneDocument } from "./defaults";

export function ScenesPage() {
  const navigate = useNavigate();
  const { data: scenes, isLoading } = useScenes();
  const createScene = useCreateScene();
  const deleteScene = useDeleteScene();
  const [busyId, setBusyId] = useState<string | null>(null);

  async function create() {
    try {
      const scene = await createScene.mutateAsync({
        name: "Untitled scene",
        description: "",
        model: "flagship",
        document: newSceneDocument(),
      });
      navigate(`/scenes/${scene.id}`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not create scene");
    }
  }

  async function duplicate(scene: Scene) {
    setBusyId(scene.id);
    try {
      const copy = await createScene.mutateAsync({
        name: `Copy of ${scene.name}`,
        description: scene.description,
        model: scene.model,
        document: scene.document as SceneDocument,
      });
      toast.success("Scene duplicated");
      navigate(`/scenes/${copy.id}`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not duplicate scene");
    } finally {
      setBusyId(null);
    }
  }

  async function remove(scene: Scene) {
    if (!confirm(`Delete “${scene.name}”? This cannot be undone.`)) return;
    setBusyId(scene.id);
    try {
      await deleteScene.mutateAsync(scene.id);
      toast.success("Scene deleted");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not delete scene");
    } finally {
      setBusyId(null);
    }
  }

  return (
    <>
      <PageHeader title="Scenes">
        <Button onClick={create} disabled={createScene.isPending}>
          <Plus className="h-4 w-4" /> New scene
        </Button>
      </PageHeader>

      <div className="p-6">
        {isLoading ? (
          <div className="flex justify-center py-16">
            <Spinner className="h-6 w-6" />
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {scenes?.map((scene) => (
              <Card key={scene.id} className="flex flex-col gap-3">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <div className="truncate font-medium text-neutral-100">{scene.name}</div>
                    <div className="mt-0.5 text-xs text-neutral-500">
                      {scene.rows}×{scene.cols} · {scene.model}
                    </div>
                  </div>
                  {scene.is_system && (
                    <Badge tone="info" className="shrink-0">
                      <Lock className="mr-1 h-3 w-3" /> System
                    </Badge>
                  )}
                </div>

                {scene.required_variables.length > 0 && (
                  <div className="text-xs text-neutral-500">
                    {scene.required_variables.length} variable
                    {scene.required_variables.length === 1 ? "" : "s"}
                  </div>
                )}

                <div className="mt-auto flex items-center gap-2">
                  {scene.is_system ? (
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => duplicate(scene)}
                      disabled={busyId === scene.id}
                    >
                      <Copy className="h-3.5 w-3.5" /> Duplicate to edit
                    </Button>
                  ) : (
                    <>
                      <Button size="sm" onClick={() => navigate(`/scenes/${scene.id}`)}>
                        Edit
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => duplicate(scene)}
                        disabled={busyId === scene.id}
                      >
                        <Copy className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="text-red-400"
                        onClick={() => remove(scene)}
                        disabled={busyId === scene.id}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </>
                  )}
                </div>
              </Card>
            ))}
            {scenes?.length === 0 && (
              <p className="text-sm text-neutral-500">No scenes yet. Create one to get started.</p>
            )}
          </div>
        )}
      </div>
    </>
  );
}
