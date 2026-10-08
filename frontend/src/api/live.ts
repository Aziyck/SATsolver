import type { QueryClient } from "@tanstack/react-query";
import { create } from "zustand";
import type { BenchmarkRow, JobDetail, JobSummary, LiveEvent, LogLine, ServerMessage } from "./types";

const MAX_LIVE_LOG_LINES = 2000;

interface LiveState {
  connected: boolean;
  jobs: Record<number, JobSummary>;
  logs: Record<number, LogLine[]>;
  setConnected: (connected: boolean) => void;
  setJobs: (jobs: JobSummary[]) => void;
  upsertJob: (job: JobSummary) => void;
  removeJob: (id: number) => void;
  appendLogs: (id: number, lines: LogLine[]) => void;
  seedLogs: (id: number, lines: LogLine[]) => void;
}

/** Live state fed by the /api/ws event stream: job summaries and streamed log lines. */
export const useLive = create<LiveState>((set) => ({
  connected: false,
  jobs: {},
  logs: {},
  setConnected: (connected) => set({ connected }),
  setJobs: (jobs) => set({ jobs: Object.fromEntries(jobs.map((job) => [job.id, job])) }),
  upsertJob: (job) =>
    set((state) => (isNewer(job, state.jobs[job.id]) ? { jobs: { ...state.jobs, [job.id]: job } } : state)),
  removeJob: (id) =>
    set((state) => {
      const jobs = { ...state.jobs };
      const logs = { ...state.logs };
      delete jobs[id];
      delete logs[id];
      return { jobs, logs };
    }),
  appendLogs: (id, lines) =>
    set((state) => {
      const next = [...(state.logs[id] ?? []), ...lines];
      return { logs: { ...state.logs, [id]: next.slice(-MAX_LIVE_LOG_LINES) } };
    }),
  seedLogs: (id, lines) =>
    set((state) => {
      const current = state.logs[id] ?? [];
      return current.length >= lines.length ? state : { logs: { ...state.logs, [id]: lines.slice(-MAX_LIVE_LOG_LINES) } };
    }),
}));

/** True when `incoming` is at least as new as `current` (HTTP replies can arrive after newer events). */
export function isNewer(incoming: Pick<JobSummary, "rev">, current: Pick<JobSummary, "rev"> | undefined): boolean {
  return !current || (incoming.rev ?? 0) >= (current.rev ?? 0);
}

// Events that arrive while a job or its rows are being fetched may be newer than
// the snapshot the server is about to return. They are kept here and merged into
// the snapshot when it lands (see mergeJobSnapshot / mergeRowsSnapshot).
interface Pending {
  instance?: JobDetail["instance"];
  result?: JobDetail["result"];
  rows: BenchmarkRow[];
}
const fetching = new Map<number, number>();
const pending = new Map<number, Pending>();

/** Wrap a fetch of job `id` so that events arriving meanwhile are not lost. */
export async function trackFetch<T>(id: number, load: () => Promise<T>): Promise<T> {
  fetching.set(id, (fetching.get(id) ?? 0) + 1);
  try {
    return await load();
  } finally {
    const left = (fetching.get(id) ?? 1) - 1;
    if (left > 0) fetching.set(id, left);
    else fetching.delete(id);
  }
}

function stash(id: number): Pending | null {
  if (!fetching.has(id)) return null;
  let entry = pending.get(id);
  if (!entry) {
    entry = { rows: [] };
    pending.set(id, entry);
  }
  return entry;
}

function takePending(id: number): Pending | undefined {
  const entry = pending.get(id);
  if (entry && !fetching.has(id)) pending.delete(id);
  return entry;
}

/** Bring a freshly fetched job up to date with events that raced the request. */
export function mergeJobSnapshot(job: JobDetail): JobDetail {
  const extra = takePending(job.id);
  const summary = useLive.getState().jobs[job.id];
  let merged = job;
  if (summary && (summary.rev ?? 0) > (job.rev ?? 0)) merged = { ...merged, ...summary };
  if (extra) {
    merged = { ...merged, instance: merged.instance ?? extra.instance ?? null, result: merged.result ?? extra.result ?? null };
  }
  return merged;
}

/** Append rows that were streamed while the row list was being fetched. */
export function mergeRowsSnapshot<T extends { rows: BenchmarkRow[] }>(id: number, data: T): T {
  const extra = takePending(id);
  if (!extra?.rows.length) return data;
  return { ...data, rows: appendRows(data.rows, extra.rows) };
}

function appendRows(current: BenchmarkRow[], incoming: BenchmarkRow[]): BenchmarkRow[] {
  const known = new Set(current.map((row) => row.index));
  const fresh = incoming.filter((row) => !known.has(row.index));
  return fresh.length ? [...current, ...fresh] : current;
}

export function sortedJobs(jobs: Record<number, JobSummary>): JobSummary[] {
  return Object.values(jobs).sort((a, b) => b.id - a.id);
}

export function applyEvents(events: LiveEvent[], queryClient: QueryClient) {
  const live = useLive.getState();
  const logBatches = new Map<number, LogLine[]>();
  const rowBatches = new Map<number, BenchmarkRow[]>();

  for (const event of events) {
    switch (event.type) {
      case "job": {
        live.upsertJob(event.job);
        queryClient.setQueryData<JobDetail>(["job", event.job.id], (old) =>
          old && isNewer(event.job, old) ? { ...old, ...event.job } : old,
        );
        break;
      }
      case "log": {
        const batch = logBatches.get(event.job_id) ?? [];
        batch.push(event.line);
        logBatches.set(event.job_id, batch);
        break;
      }
      case "instance": {
        const entry = stash(event.job_id);
        if (entry) entry.instance = event.instance;
        queryClient.setQueryData<JobDetail>(["job", event.job_id], (old) => (old ? { ...old, instance: event.instance } : old));
        break;
      }
      case "result": {
        const entry = stash(event.job_id);
        if (entry) entry.result = event.result;
        queryClient.setQueryData<JobDetail>(["job", event.job_id], (old) => (old ? { ...old, result: event.result } : old));
        break;
      }
      case "row": {
        const batch = rowBatches.get(event.job_id) ?? [];
        batch.push(event.row);
        rowBatches.set(event.job_id, batch);
        break;
      }
      case "deleted":
        pending.delete(event.job_id);
        live.removeJob(event.job_id);
        queryClient.removeQueries({ queryKey: ["job", event.job_id] });
        queryClient.removeQueries({ queryKey: ["rows", event.job_id] });
        break;
      case "numbering_reset":
        // Job numbers start again at 1: nothing cached under an old number may survive.
        queryClient.removeQueries({ queryKey: ["job"] });
        queryClient.removeQueries({ queryKey: ["rows"] });
        queryClient.removeQueries({ queryKey: ["case"] });
        break;
      case "resync":
        void queryClient.invalidateQueries();
        break;
    }
  }

  logBatches.forEach((lines, id) => live.appendLogs(id, lines));
  rowBatches.forEach((rows, id) => {
    stash(id)?.rows.push(...rows);
    queryClient.setQueryData<{ rows: BenchmarkRow[] }>(["rows", id], (old) => {
      if (!old) return old;
      const next = appendRows(old.rows, rows);
      return next === old.rows ? old : { ...old, rows: next };
    });
  });
}

/** Connect to the event stream and keep reconnecting. Returns a cleanup function. */
export function startLiveConnection(queryClient: QueryClient): () => void {
  let socket: WebSocket | null = null;
  let stopped = false;
  let retry = 0;
  let timer: ReturnType<typeof setTimeout> | undefined;

  const connect = () => {
    if (stopped) return;
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    socket = new WebSocket(`${protocol}://${window.location.host}/api/ws`);
    socket.onopen = () => {
      retry = 0;
      useLive.getState().setConnected(true);
    };
    socket.onmessage = (message) => {
      const data = JSON.parse(message.data as string) as ServerMessage;
      if (data.type === "hello") {
        useLive.getState().setJobs(data.jobs);
        // Anything cached may be stale after a reconnect.
        void queryClient.invalidateQueries({ queryKey: ["job"] });
        void queryClient.invalidateQueries({ queryKey: ["rows"] });
      } else if (data.type === "batch") {
        applyEvents(data.events, queryClient);
      }
    };
    socket.onclose = () => {
      useLive.getState().setConnected(false);
      if (stopped) return;
      retry = Math.min(retry + 1, 6);
      timer = setTimeout(connect, 500 * 2 ** retry);
    };
  };

  connect();
  return () => {
    stopped = true;
    if (timer) clearTimeout(timer);
    socket?.close();
  };
}
