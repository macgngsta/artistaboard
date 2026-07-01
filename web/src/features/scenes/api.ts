import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { PreviewOut, Scene, SceneIn, SceneDocument } from "@/api/types";

const scenesKey = ["scenes"] as const;

export function useScenes() {
  return useQuery({
    queryKey: scenesKey,
    queryFn: async () => unwrap(await api.GET("/scenes")),
  });
}

export function useScene(sceneId: string | undefined) {
  return useQuery({
    queryKey: ["scenes", sceneId],
    enabled: !!sceneId,
    queryFn: async () =>
      unwrap(await api.GET("/scenes/{scene_id}", { params: { path: { scene_id: sceneId! } } })),
  });
}

export function useCreateScene() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: SceneIn) => unwrap(await api.POST("/scenes", { body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: scenesKey }),
  });
}

export function useUpdateScene() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: SceneIn }) =>
      unwrap(await api.PUT("/scenes/{scene_id}", { params: { path: { scene_id: id } }, body })),
    onSuccess: (scene: Scene) => {
      qc.invalidateQueries({ queryKey: scenesKey });
      qc.setQueryData(["scenes", scene.id], scene);
    },
  });
}

export function useDeleteScene() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      unwrap(await api.DELETE("/scenes/{scene_id}", { params: { path: { scene_id: id } } }));
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: scenesKey }),
  });
}

// The server render is the single source of truth for the canvas. Callers debounce
// the payload and key a useQuery on it; keepPreviousData preserves the last good
// frame while a new render is in flight or has failed with a 422.
export async function previewScene(
  document: SceneDocument,
  sample_data: Record<string, unknown>,
): Promise<PreviewOut> {
  return unwrap(await api.POST("/preview", { body: { document, sample_data } }));
}
