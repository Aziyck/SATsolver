import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Catalog, JobDetail, SolveResult } from "../api/types";
import { field } from "../test/fields";
import { renderWithApp } from "../test/render";
import { SolveResultPanel } from "./SolveResultPanel";

const CATALOG: Catalog = {
  version: "test",
  problems: [],
  solvers: [
    {
      key: "cdcl",
      title: "CDCL",
      complete: true,
      summary: "Conflict-driven clause learning.",
      description: "",
      fields: [field({ name: "restarts", label: "Restarts", kind: "bool", default: true })],
    },
  ],
  presets: [],
  log_levels: ["normal"],
  limits: { max_clauses: 1, max_benchmark_runs: 1, max_workers: 1 },
  defaults: { solve_timeout: 60, benchmark_timeout: 10, benchmark_rules: [] },
};

/** A solve job as GET /api/jobs/7 returns it; each test changes what it is about. */
function job(partial: Partial<JobDetail>): JobDetail {
  return {
    id: 7,
    rev: 1,
    label: "J7",
    kind: "solve",
    title: "Sudoku 4x4",
    status: "done",
    created_at: "2026-11-15T10:00:00Z",
    started_at: "2026-11-15T10:00:01Z",
    finished_at: "2026-11-15T10:00:02Z",
    progress: { current: 0, total: 0, message: "" },
    row_count: 0,
    problems: ["sudoku"],
    solver: "cdcl",
    error: null,
    request: { problem: "sudoku", params: {}, solver: "cdcl", options: {} } as JobDetail["request"],
    instance: null,
    result: null,
    errors: null,
    logs: [],
    log_count: 0,
    ...partial,
    // The summary fields mirror the result, as in a real reply.
    result_status: partial.result?.status ?? null,
    verified: partial.result?.verified ?? null,
    elapsed: partial.result?.elapsed ?? null,
  };
}

function result(partial: Partial<SolveResult>): SolveResult {
  return {
    solver: "cdcl",
    solver_label: "CDCL",
    options: {},
    options_summary: "",
    status: "SAT",
    elapsed: 0.01,
    stats: { decisions: 3 },
    decoded: null,
    verified: null,
    check_errors: [],
    expected: null,
    timeout: 60,
    error: null,
    model_file: null,
    ...partial,
  };
}

function renderJob(detail: JobDetail) {
  return renderWithApp(<SolveResultPanel jobId={detail.id} onEdit={() => {}} onOpenAs={() => {}} onDeleted={() => {}} />, {
    queryData: [
      [["job", detail.id], detail],
      [["catalog"], CATALOG],
    ],
  });
}

describe("SolveResultPanel", () => {
  it("shows progress and a Stop button while the job runs", () => {
    renderJob(job({ status: "running", finished_at: null, progress: { current: 0, total: 0, message: "Solving with CDCL" } }));
    expect(screen.getByRole("progressbar")).toBeTruthy();
    expect(screen.getByText(/Solving with CDCL/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Stop" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Rerun" })).toBeNull();
  });

  it("shows a verified SAT answer", () => {
    renderJob(job({ result: result({ status: "SAT", verified: true }) }));
    expect(screen.getByText("SAT")).toBeTruthy();
    expect(screen.getByText("Verified")).toBeTruthy();
    expect(screen.queryByRole("progressbar")).toBeNull();
    expect(screen.getByRole("button", { name: "Rerun" })).toBeTruthy();
  });

  it("raises an alert when the answer fails its checks", () => {
    renderJob(job({ result: result({ status: "SAT", verified: false, check_errors: ["Row 2 has two 4s."] }) }));
    expect(screen.getByText("The answer did not pass the checks")).toBeTruthy();
    expect(screen.getByText("Row 2 has two 4s.")).toBeTruthy();
    expect(screen.getByText("Failed")).toBeTruthy();
    expect(screen.queryByText("Verified")).toBeNull();
  });

  it("shows UNKNOWN as UNKNOWN, never as UNSAT", () => {
    renderJob(job({ result: result({ status: "UNKNOWN", solver: "walksat", solver_label: "WalkSAT" }) }));
    expect(screen.getByText("UNKNOWN")).toBeTruthy();
    expect(screen.getByText(/Stopped without an answer/)).toBeTruthy();
    expect(screen.queryByText("UNSAT")).toBeNull();
    // "Proof" is what the Check column says for UNSAT.
    expect(screen.queryByText("Proof")).toBeNull();
  });

  it("shows the error of a failed job", () => {
    renderJob(job({ status: "failed", error: "Invalid parameters.", errors: { size: "must be 4 or 9" } }));
    expect(screen.getByText("The job failed")).toBeTruthy();
    expect(screen.getByText("Invalid parameters.")).toBeTruthy();
    expect(screen.getByText("size: must be 4 or 9")).toBeTruthy();
  });

  it("has a Settings tab only for a job with a solver", () => {
    const { unmount } = renderJob(job({ result: result({ status: "SAT" }) }));
    expect(screen.getByRole("tab", { name: "Settings" })).toBeTruthy();
    unmount();

    // The same solve job, only without a solver.
    renderJob(job({ solver: null, request: { problem: "sudoku", params: {} } as JobDetail["request"] }));
    expect(screen.queryByRole("tab", { name: "Settings" })).toBeNull();
    expect(screen.getByRole("tab", { name: "Log" })).toBeTruthy();
  });
});
