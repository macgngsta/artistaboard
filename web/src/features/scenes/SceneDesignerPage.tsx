import { useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Save, Copy, AlertTriangle } from "lucide-react";
import { PageHeader } from "@/components/AppLayout";
import { BoardGrid } from "@/components/BoardGrid";
import { Button, Card, Input, Spinner } from "@/components/ui/primitives";
import { toast } from "@/components/ui/toast";
import { ApiError } from "@/api/errors";
import type { RequiredVariable, SceneDocument, SceneIn } from "@/api/types";
import { useDebounced } from "@/lib/useDebounced";
import { useScene, useUpdateScene, useCreateScene, previewScene } from "./api";
import { useSceneEditor } from "./store";
import { collectVariables } from "./variables";
import { GridEditor } from "./GridEditor";
import { RegionEditor } from "./RegionEditor";
import { SampleDataForm } from "./SampleDataForm";

export function SceneDesignerPage() {
  const { sceneId } = useParams();
  const navigate = useNavigate();
  const { data: scene, isLoading, error } = useScene(sceneId);

  const ed = useSceneEditor();
  const updateScene = useUpdateScene();
  const createScene = useCreateScene();

  // Load into the editor store once per scene id.
  useEffect(() => {
    if (scene && scene.id !== ed.loadedId) ed.load(scene);
  }, [scene, ed]);

  // Debounced live preview — the server render is the source of truth.
  const debouncedDoc = useDebounced(ed.document, 300);
  const debouncedSample = useDebounced(ed.sampleData, 300);
  const preview = useQuery({
    queryKey: ["preview", debouncedDoc, debouncedSample],
    enabled: ed.loadedId === sceneId,
    queryFn: () => previewScene(debouncedDoc, debouncedSample),
    placeholderData: (prev) => prev, // keep the last good frame on a 422
    retry: false,
  });

  if (isLoading || ed.loadedId !== sceneId) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        {error ? (
          <p className="text-sm text-red-400">
            {error instanceof ApiError ? error.message : "Failed to load scene"}
          </p>
        ) : (
          <Spinner className="h-6 w-6" />
        )}
      </div>
    );
  }

  const readOnly = ed.isSystem;
  const serverVars = (scene?.required_variables ?? []) as unknown as RequiredVariable[];
  const variables = collectVariables(ed.document, serverVars);
  const previewError = preview.error instanceof ApiError ? preview.error.message : null;

  async function save() {
    const body: SceneIn = {
      name: ed.name || "Untitled scene",
      description: ed.description,
      model: ed.model,
      document: ed.document as SceneDocument,
    };
    try {
      await updateScene.mutateAsync({ id: ed.loadedId!, body });
      toast.success("Scene saved");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not save scene");
    }
  }

  async function duplicate() {
    try {
      const copy = await createScene.mutateAsync({
        name: `Copy of ${ed.name}`,
        description: ed.description,
        model: ed.model,
        document: ed.document as SceneDocument,
      });
      toast.success("Duplicated — now editable");
      navigate(`/scenes/${copy.id}`);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not duplicate scene");
    }
  }

  return (
    <>
      <PageHeader title="Scene designer">
        <Button variant="ghost" size="sm" onClick={() => navigate("/scenes")}>
          <ArrowLeft className="h-4 w-4" /> Scenes
        </Button>
        {readOnly ? (
          <Button onClick={duplicate} disabled={createScene.isPending}>
            <Copy className="h-4 w-4" /> Duplicate to edit
          </Button>
        ) : (
          <Button onClick={save} disabled={updateScene.isPending || !ed.dirty}>
            {updateScene.isPending ? <Spinner /> : <Save className="h-4 w-4" />} Save
          </Button>
        )}
      </PageHeader>

      {readOnly && (
        <div className="flex items-center gap-2 border-b border-amber-900/50 bg-amber-950/30 px-6 py-2 text-sm text-amber-300">
          <AlertTriangle className="h-4 w-4" /> System scene — read-only. Duplicate it to make changes.
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 p-6 lg:grid-cols-[320px_1fr_320px]">
        {/* Left: grid + regions */}
        <Card className="flex flex-col gap-4">
          <Input
            value={ed.name}
            readOnly={readOnly}
            onChange={(e) => ed.setName(e.target.value)}
            placeholder="Scene name"
            className="font-medium"
          />
          <GridEditor readOnly={readOnly} />
        </Card>

        {/* Center: live preview */}
        <div className="flex flex-col items-center gap-3">
          <div className="text-xs uppercase tracking-wide text-neutral-500">Live preview</div>
          {preview.data ? (
            <BoardGrid characters={preview.data.characters} className="w-full max-w-2xl" />
          ) : (
            <div className="flex h-40 items-center justify-center">
              <Spinner className="h-6 w-6" />
            </div>
          )}
          {previewError && (
            <div className="flex items-center gap-2 rounded-md border border-red-900 bg-red-950/50 px-3 py-2 text-sm text-red-300">
              <AlertTriangle className="h-4 w-4 shrink-0" /> {previewError}
            </div>
          )}
        </div>

        {/* Right: region config + sample data */}
        <div className="flex flex-col gap-4">
          <Card>
            <RegionEditor readOnly={readOnly} />
          </Card>
          <Card>
            <div className="mb-3 text-sm font-medium text-neutral-200">Sample data</div>
            <SampleDataForm variables={variables} />
          </Card>
        </div>
      </div>
    </>
  );
}
