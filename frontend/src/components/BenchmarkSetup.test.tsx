import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { BenchmarkRequest, Catalog, RunEnvironment, SolverSpec } from "../api/types";
import { field } from "../test/fields";
import { renderWithApp } from "../test/render";
import { BenchmarkSetup, entryForRow } from "./BenchmarkSetup";

const CDCL: SolverSpec = {
  key: "cdcl",
  title: "CDCL",
  complete: true,
  summary: "Conflict-driven clause learning.",
  description: "",
  fields: [field({ name: "restart_interval", label: "Restart interval", kind: "int", default: 100, unit: "conflicts" })],
};

const CATALOG: Catalog = {
  version: "test",
  problems: [],
  solvers: [CDCL],
  stats: [],
  presets: [],
  log_levels: ["normal"],
  limits: { max_clauses: 1, max_benchmark_runs: 1, max_workers: 1 },
  defaults: { solve_timeout: 1, benchmark_timeout: 1, benchmark_rules: [] },
};

function request(solvers: BenchmarkRequest["solvers"], rules: BenchmarkRequest["rules"] = []): BenchmarkRequest {
  return { problems: ["sudoku"], segments: [{}], solvers, repeats: 1, timeout: 10, rules };
}

/** True when `first` comes before `second` in the page. */
const before = (first: Node, second: Node) => Boolean(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING);

const ENVIRONMENT: RunEnvironment = {
  python_implementation: "PyPy",
  python_version: "3.10.14",
  os: "Linux 6.8.0 (x86_64)",
  cpu_model: "Test CPU",
  cpu_logical_cores: 4,
  cpu_physical_cores: null,
  ram_total_gb: 8,
  wizsat_version: "2.0.0",
  git_commit: "abc1234",
  git_dirty: true,
};

describe("BenchmarkSetup", () => {
  it("shows the machine the benchmark ran on, or that it was not recorded", () => {
    const { unmount } = renderWithApp(<BenchmarkSetup request={request([{ solver: "cdcl" }])} catalog={CATALOG} environment={ENVIRONMENT} />);
    expect(screen.getByText("PyPy 3.10.14")).toBeTruthy();
    expect(screen.getByText("Test CPU")).toBeTruthy();
    expect(screen.getByText("2.0.0, commit abc1234 with uncommitted changes")).toBeTruthy();
    unmount();

    renderWithApp(<BenchmarkSetup request={request([{ solver: "cdcl" }])} catalog={CATALOG} environment={null} />);
    expect(screen.getByText(/not recorded/)).toBeTruthy();
  });

  it("lists every solver entry with its label and its options", () => {
    const solvers = [
      { solver: "cdcl", label: "CDCL fast", options: { restart_interval: 50 } },
      { solver: "cdcl", options: { restart_interval: 400 } },
      { solver: "gone" },
    ];
    renderWithApp(<BenchmarkSetup request={request(solvers)} catalog={CATALOG} environment={null} />);

    const fast = screen.getByText("CDCL fast");
    const plain = screen.getByText("CDCL");
    const gone = screen.getByText("gone");
    const fastOptions = screen.getByText("50 conflicts");
    const plainOptions = screen.getByText("400 conflicts");
    // Each entry's options follow its own label, in request order.
    expect(before(fast, fastOptions) && before(fastOptions, plain)).toBe(true);
    expect(before(plain, plainOptions) && before(plainOptions, gone)).toBe(true);
    expect(screen.getByText("This solver is no longer available.")).toBeTruthy();
  });

  it("says None when there are no limit rules", () => {
    renderWithApp(<BenchmarkSetup request={request([{ solver: "cdcl" }])} catalog={CATALOG} environment={null} />);
    expect(screen.getByText(/^None: every solver ran every case/)).toBeTruthy();
  });

  it("lists the limit rules when there are some", () => {
    const rules = [{ solver: "cdcl", action: "skip" as const, min_variables: 200, seconds: null }];
    renderWithApp(<BenchmarkSetup request={request([{ solver: "cdcl" }], rules)} catalog={CATALOG} environment={null} />);
    expect(screen.getByText("CDCL: skip from 200 variables")).toBeTruthy();
    expect(screen.queryByText(/^None: every solver/)).toBeNull();
  });
});

describe("entryForRow", () => {
  // Rows are numbered case index x number of solvers + solver position.
  it.each([
    { entries: 1, rows: [0, 1, 2], positions: [0, 0, 0] },
    { entries: 2, rows: [0, 1, 2, 3], positions: [0, 1, 0, 1] },
    { entries: 3, rows: [0, 1, 2, 3, 4, 5, 7], positions: [0, 1, 2, 0, 1, 2, 1] },
  ])("maps rows to solver entries with $entries entries", ({ entries, rows, positions }) => {
    const solvers = Array.from({ length: entries }, (_, position) => ({ solver: "cdcl", label: `entry ${position}` }));
    const req = request(solvers);
    expect(rows.map((row) => entryForRow(req, row)?.label)).toEqual(positions.map((position) => `entry ${position}`));
  });

  it("has no entry when the request lists no solvers", () => {
    expect(entryForRow(request([]), 0)).toBeUndefined();
  });
});
