import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { PipelineIn } from "@/api/types";

const pipelinesKey = ["pipelines"] as const;

export function usePipelines() {
  return useQuery({
    queryKey: pipelinesKey,
    queryFn: async () => unwrap(await api.GET("/pipelines")),
  });
}

export function usePipeline(pipelineId: string | undefined) {
  return useQuery({
    queryKey: ["pipelines", pipelineId],
    enabled: !!pipelineId,
    queryFn: async () =>
      unwrap(
        await api.GET("/pipelines/{pipeline_id}", {
          params: { path: { pipeline_id: pipelineId! } },
        }),
      ),
  });
}

export function useCreatePipeline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: PipelineIn) => unwrap(await api.POST("/pipelines", { body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: pipelinesKey }),
  });
}

export function useUpdatePipeline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: PipelineIn }) =>
      unwrap(
        await api.PUT("/pipelines/{pipeline_id}", {
          params: { path: { pipeline_id: id } },
          body,
        }),
      ),
    onSuccess: (pipeline) => {
      qc.invalidateQueries({ queryKey: pipelinesKey });
      qc.setQueryData(["pipelines", pipeline.id], pipeline);
    },
  });
}

export function useDeletePipeline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      unwrap(await api.DELETE("/pipelines/{pipeline_id}", { params: { path: { pipeline_id: id } } }));
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: pipelinesKey }),
  });
}
