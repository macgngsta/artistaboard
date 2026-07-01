import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import type { BoardIn } from "@/api/types";

const boardsKey = ["boards"] as const;

export function useBoards() {
  return useQuery({
    queryKey: boardsKey,
    queryFn: async () => unwrap(await api.GET("/boards")),
  });
}

export function useCreateBoard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: BoardIn) => unwrap(await api.POST("/boards", { body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: boardsKey }),
  });
}

export function useUpdateBoard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ id, body }: { id: string; body: BoardIn }) =>
      unwrap(await api.PUT("/boards/{board_id}", { params: { path: { board_id: id } }, body })),
    onSuccess: () => qc.invalidateQueries({ queryKey: boardsKey }),
  });
}

export function useDeleteBoard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      unwrap(await api.DELETE("/boards/{board_id}", { params: { path: { board_id: id } } }));
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: boardsKey }),
  });
}

export function useTestBoard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) =>
      unwrap(await api.POST("/boards/{board_id}/test", { params: { path: { board_id: id } } })),
    onSuccess: () => qc.invalidateQueries({ queryKey: boardsKey }),
  });
}

const runKey = (boardId: string) => ["boards", boardId, "run"] as const;

// Poll the "now playing" state for a board. `pollMs` enables live refresh only
// while a run view is on screen; a 404 (no pipeline assigned) resolves to null.
export function useBoardRun(boardId: string | undefined, pollMs?: number) {
  return useQuery({
    queryKey: boardId ? runKey(boardId) : ["boards", "run", "none"],
    enabled: !!boardId,
    refetchInterval: pollMs ?? false,
    queryFn: async () => {
      const { data, response } = await api.GET("/boards/{board_id}/run", {
        params: { path: { board_id: boardId! } },
      });
      if (response.status === 404) return null;
      return data ?? null;
    },
  });
}

// assign takes pipeline_id as a QUERY param (not a body).
export function useAssignPipeline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async ({ boardId, pipelineId }: { boardId: string; pipelineId: string }) =>
      unwrap(
        await api.POST("/boards/{board_id}/assign", {
          params: { path: { board_id: boardId }, query: { pipeline_id: pipelineId } },
        }),
      ),
    onSuccess: (_d, { boardId }) => qc.invalidateQueries({ queryKey: runKey(boardId) }),
  });
}

export function useStartBoard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (boardId: string) =>
      unwrap(await api.POST("/boards/{board_id}/start", { params: { path: { board_id: boardId } } })),
    onSuccess: (_d, boardId) => {
      qc.invalidateQueries({ queryKey: runKey(boardId) });
      qc.invalidateQueries({ queryKey: boardsKey });
    },
  });
}

export function useStopBoard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (boardId: string) =>
      unwrap(await api.POST("/boards/{board_id}/stop", { params: { path: { board_id: boardId } } })),
    onSuccess: (_d, boardId) => {
      qc.invalidateQueries({ queryKey: runKey(boardId) });
      qc.invalidateQueries({ queryKey: boardsKey });
    },
  });
}
