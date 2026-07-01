import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";

const dataSourcesKey = ["data", "sources"] as const;

// Active data series (source + fetch-defining key) referenced by the user's running
// boards, each with its snapshot freshness. Polled periodically so the Jobs page shows
// ageing freshness without a manual refresh.
export function useDataSources() {
  return useQuery({
    queryKey: dataSourcesKey,
    refetchInterval: 30_000,
    queryFn: async () => unwrap(await api.GET("/data/sources")),
  });
}

// Kick a manual poll of every referenced source; on success refresh freshness so the
// just-written snapshots show as fresh.
export function usePollNow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => unwrap(await api.POST("/data/poll")),
    onSuccess: () => qc.invalidateQueries({ queryKey: dataSourcesKey }),
  });
}
