import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap } from "@/api/client";
import { ApiError } from "@/api/errors";
import type { User } from "@/api/types";

export const meKey = ["auth", "me"] as const;

// GET /auth/me. A 401 (unauthenticated) is a normal state, not an error to retry,
// so we swallow it into `null` and let route guards redirect.
export function useSession() {
  return useQuery<User | null>({
    queryKey: meKey,
    queryFn: async () => {
      try {
        return unwrap(await api.GET("/auth/me"));
      } catch (e) {
        if (e instanceof ApiError && e.status === 401) return null;
        throw e;
      }
    },
    staleTime: 30_000,
  });
}

export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { email: string; password: string }) =>
      unwrap(await api.POST("/auth/login", { body })),
    onSuccess: (user) => qc.setQueryData(meKey, user),
  });
}

export function useRegister() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (body: { email: string; password: string; display_name?: string }) =>
      unwrap(await api.POST("/auth/register", { body: { display_name: "", ...body } })),
    onSuccess: (user) => qc.setQueryData(meKey, user),
  });
}

export function useLogout() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await api.POST("/auth/logout");
    },
    onSuccess: () => {
      qc.setQueryData(meKey, null);
      qc.clear();
    },
  });
}
