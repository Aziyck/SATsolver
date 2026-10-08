import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { notifications } from "@mantine/notifications";
import { api, ApiError } from "./client";
import { mergeJobSnapshot, mergeRowsSnapshot, trackFetch, useLive } from "./live";
import type { JobKind, ProblemSpec, SolverSpec } from "./types";

export function useCatalog() {
  return useQuery({ queryKey: ["catalog"], queryFn: api.catalog, staleTime: Infinity });
}

export function useProblem(key: string | undefined): ProblemSpec | undefined {
  const { data } = useCatalog();
  return data?.problems.find((problem) => problem.key === key);
}

export function useSolverSpecs(): Record<string, SolverSpec> {
  const { data } = useCatalog();
  return Object.fromEntries((data?.solvers ?? []).map((solver) => [solver.key, solver]));
}

export function useJob(id: number | null | undefined) {
  const seedLogs = useLive((state) => state.seedLogs);
  return useQuery({
    queryKey: ["job", id],
    queryFn: async () => {
      const job = mergeJobSnapshot(await trackFetch(id as number, () => api.job(id as number)));
      seedLogs(job.id, job.logs);
      return job;
    },
    enabled: typeof id === "number" && id > 0,
  });
}

export function useRows(id: number | null | undefined) {
  return useQuery({
    queryKey: ["rows", id],
    queryFn: async () => mergeRowsSnapshot(id as number, await trackFetch(id as number, () => api.rows(id as number))),
    enabled: typeof id === "number" && id > 0,
  });
}

function notifyError(title: string) {
  return (error: unknown) => {
    const message = error instanceof ApiError ? error.message : String(error);
    notifications.show({ color: "red", title, message });
  };
}

export function useCreateJob() {
  const upsertJob = useLive((state) => state.upsertJob);
  return useMutation({
    mutationFn: ({ kind, body, title }: { kind: JobKind; body: unknown; title?: string }) => api.createJob(kind, body, title),
    onSuccess: (job) => upsertJob(job),
  });
}

export function useJobActions() {
  const queryClient = useQueryClient();
  const upsertJob = useLive((state) => state.upsertJob);
  const removeJob = useLive((state) => state.removeJob);

  const cancel = useMutation({ mutationFn: api.cancel, onSuccess: upsertJob, onError: notifyError("Could not cancel") });
  const skip = useMutation({ mutationFn: api.skip, onSuccess: upsertJob, onError: notifyError("Could not skip") });
  const rerun = useMutation({ mutationFn: api.rerun, onSuccess: upsertJob, onError: notifyError("Could not rerun") });
  const remove = useMutation({
    mutationFn: api.remove,
    onSuccess: (_data, id) => {
      removeJob(id);
      queryClient.removeQueries({ queryKey: ["job", id] });
      queryClient.removeQueries({ queryKey: ["rows", id] });
    },
    onError: notifyError("Could not delete"),
  });
  const clear = useMutation({
    mutationFn: api.clear,
    onSuccess: (data) => data.deleted.forEach((id) => removeJob(id)),
    onError: notifyError("Could not clear jobs"),
  });
  const resetNumbering = useMutation({ mutationFn: api.resetNumbering, onError: notifyError("Could not restart the numbering") });
  return { cancel, skip, rerun, remove, clear, resetNumbering };
}
