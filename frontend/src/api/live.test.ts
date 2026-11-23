import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it } from "vitest";
import { applyEvents, mergeJobSnapshot, mergeRowsSnapshot, trackFetch, useLive } from "./live";
import type { BenchmarkRow, JobDetail, JobSummary, RunEnvironment, SolveResult } from "./types";

function summary(partial: Partial<JobSummary>): JobSummary {
  return {
    id: 1,
    rev: 1,
    label: "J1",
    kind: "solve",
    title: "",
    status: "queued",
    created_at: "",
    started_at: null,
    finished_at: null,
    progress: { current: null, total: null, message: "" },
    row_count: 0,
    problems: [],
    solver: null,
    interpreter: null,
    result_status: null,
    verified: null,
    elapsed: null,
    error: null,
    ...partial,
  };
}

function detail(partial: Partial<JobDetail>): JobDetail {
  return { ...summary(partial), request: {} as JobDetail["request"], instance: null, result: null, errors: null, environment: null, logs: [], log_count: 0, ...partial };
}

const RESULT = { status: "SAT" } as SolveResult;

const ENVIRONMENT: RunEnvironment = {
  python_implementation: "CPython",
  python_version: "3.12.0",
  os: "Linux 6.8.0 (x86_64)",
  cpu_model: "Test CPU",
  cpu_logical_cores: 8,
  cpu_physical_cores: 4,
  ram_total_gb: 15.5,
  wizsat_version: "2.0.0",
  git_commit: "0000000",
  git_dirty: false,
};

/** A fetch whose reply was produced before the events below were sent. */
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((done) => (resolve = done));
  return { promise, resolve };
}

describe("live events", () => {
  beforeEach(() => useLive.setState({ jobs: {}, logs: {} }));

  it("ignores summaries older than the one it has", () => {
    const live = useLive.getState();
    live.upsertJob(summary({ rev: 3, status: "done" }));
    live.upsertJob(summary({ rev: 1, status: "queued" }));
    expect(useLive.getState().jobs[1].status).toBe("done");
  });

  it("keeps events that arrive while the job is being fetched", async () => {
    const client = new QueryClient();
    const reply = deferred<JobDetail>();
    const pendingFetch = trackFetch(1, () => reply.promise);

    applyEvents(
      [
        { type: "result", job_id: 1, result: RESULT },
        { type: "job", job: summary({ rev: 4, status: "done", result_status: "SAT" }) },
      ],
      client,
    );
    // The server answered with its state from before the job finished.
    reply.resolve(detail({ rev: 2, status: "running" }));
    const job = mergeJobSnapshot(await pendingFetch);

    expect(job.status).toBe("done");
    expect(job.result).toEqual(RESULT);
  });

  it("merges rows streamed during a fetch without duplicates", async () => {
    const client = new QueryClient();
    const row = (index: number) => ({ index }) as BenchmarkRow;
    const reply = deferred<{ rows: BenchmarkRow[] }>();
    const pendingFetch = trackFetch(7, () => reply.promise);

    applyEvents(
      [
        { type: "row", job_id: 7, row: row(1) },
        { type: "row", job_id: 7, row: row(2) },
      ],
      client,
    );
    reply.resolve({ rows: [row(0), row(1)] });
    const data = mergeRowsSnapshot(7, await pendingFetch);
    expect(data.rows.map((item) => item.index)).toEqual([0, 1, 2]);
  });

  it("puts the environment of a job that has started into the job opened while it was queued", () => {
    // The page for a queued job has environment: null; the worker reports it later (A38).
    const client = new QueryClient();
    client.setQueryData(["job", 1], detail({ status: "queued" }));
    applyEvents([{ type: "environment", job_id: 1, environment: ENVIRONMENT }], client);
    expect(client.getQueryData<JobDetail>(["job", 1])!.environment).toEqual(ENVIRONMENT);
  });

  it("keeps an environment that arrives while the job is being fetched", async () => {
    const client = new QueryClient();
    const reply = deferred<JobDetail>();
    const pendingFetch = trackFetch(1, () => reply.promise);

    applyEvents([{ type: "environment", job_id: 1, environment: ENVIRONMENT }], client);
    // The server answered before the worker reported.
    reply.resolve(detail({ status: "queued", environment: null }));
    expect(mergeJobSnapshot(await pendingFetch).environment).toEqual(ENVIRONMENT);
  });

  it("does not let an old event overwrite a newer cached job", () => {
    const client = new QueryClient();
    client.setQueryData(["job", 1], detail({ rev: 5, status: "done" }));
    applyEvents([{ type: "job", job: summary({ rev: 4, status: "running" }) }], client);
    expect(client.getQueryData<JobDetail>(["job", 1])!.status).toBe("done");
  });
});
