import { describe, expect, it } from "vitest";
import type { BenchmarkRow, Catalog } from "../api/types";
import { statSpec } from "../test/catalog";
import { field } from "../test/fields";
import { draftFromRequest, isVisibleSweep, requestFromDraft, sweepValue } from "./benchmark";
import { formatEdges, parseEdges, toggleEdge } from "./edges";
import { formatSeconds } from "./format";
import { changedFields, defaultValues, displayValue, isDefaultValue, isVisible, parseNumberList, visibleValues } from "./params";
import {
  aggregate,
  CASE_X,
  chartMetrics,
  defaultAxes,
  filterRows,
  metricOption,
  metricValue,
  type RowFilter,
  seriesByX,
  sortRows,
  sortValue,
  statusShares,
  suspiciousRows,
  varyingParams,
} from "./stats";
import { learnLink } from "./learn";
import { conflictCells, parsePuzzle, sudokuSize } from "./sudoku";

const MODE = field({
  name: "mode",
  kind: "choice",
  default: "gnp",
  sweepable: true,
  choices: [
    { value: "gnp", label: "G(n,p)", help: "" },
    { value: "manual", label: "Manual", help: "" },
  ],
});
const P = field({ name: "p", kind: "float", default: 0.3, sweepable: true, show_if: { mode: ["gnp"] } });
const EDGES = field({ name: "edges", kind: "edges", default: "1-2", show_if: { mode: ["manual"] } });

describe("parseNumberList", () => {
  it("parses lists and ranges like the server", () => {
    expect(parseNumberList("10, 20; 30", true)).toEqual([10, 20, 30]);
    expect(parseNumberList("1..4", true)).toEqual([1, 2, 3, 4]);
    expect(parseNumberList("1 .. 3, 10", true)).toEqual([1, 2, 3, 10]);
    expect(parseNumberList("0.1..0.3:0.1", false)).toEqual([0.1, 0.2, 0.3]);
  });

  it("returns readable errors", () => {
    expect(parseNumberList("5..1", true)).toMatch(/ends before/);
    expect(parseNumberList("1.5", true)).toMatch(/whole number/);
    expect(parseNumberList("abc", false)).toMatch(/not a number/);
    expect(parseNumberList("", true)).toMatch(/at least one/);
  });
});

describe("field visibility", () => {
  it("follows show_if", () => {
    const values = defaultValues([MODE, P, EDGES]);
    expect(isVisible(P, values)).toBe(true);
    expect(isVisible(EDGES, values)).toBe(false);
    expect(visibleValues([MODE, P, EDGES], values)).toEqual({ mode: "gnp", p: 0.3 });
  });

  it("treats swept choices as any-of", () => {
    expect(isVisibleSweep(P, { mode: ["manual", "gnp"] })).toBe(true);
    expect(isVisibleSweep(P, { mode: ["manual"] })).toBe(false);
  });

  it("converts values for the benchmark form", () => {
    expect(sweepValue(P, 0.3)).toBe("0.3");
    expect(sweepValue(P, [0.1, 0.2])).toBe("0.1, 0.2");
    expect(sweepValue(MODE, "gnp, manual")).toEqual(["gnp", "manual"]);
  });
});

describe("defaults and display", () => {
  const noise = field({ name: "noise", kind: "float", default: 0.567 });
  const cb = field({ name: "cb", kind: "float", default: null, placeholder: "automatic" });
  const restarts = field({ name: "restarts", kind: "bool", default: true });
  const strategy = field({
    name: "strategy",
    kind: "choice",
    default: "luby",
    choices: [
      { value: "luby", label: "Luby sequence", help: "" },
      { value: "fixed", label: "Fixed interval", help: "" },
    ],
  });
  const timeout = field({ name: "timeout", kind: "float", default: 30, unit: "s" });

  it("treats blanks alike and compares numbers by value", () => {
    expect(isDefaultValue(noise, 0.567)).toBe(true);
    expect(isDefaultValue(noise, "0.567")).toBe(true);
    expect(isDefaultValue(noise, 0.5)).toBe(false);
    expect(isDefaultValue(cb, "")).toBe(true);
    expect(isDefaultValue(cb, undefined)).toBe(true);
    expect(isDefaultValue(cb, 3)).toBe(false);
    expect(isDefaultValue(restarts, false)).toBe(false);
  });

  it("lists only the changed fields", () => {
    const changed = changedFields([noise, cb, restarts], { noise: 0.4, cb: null, restarts: true });
    expect(changed.map((item) => item.name)).toEqual(["noise"]);
  });

  it("says values the way a person would", () => {
    expect(displayValue(cb, null)).toBe("automatic");
    expect(displayValue(restarts, false)).toBe("Off");
    expect(displayValue(strategy, "fixed")).toBe("Fixed interval");
    expect(displayValue(timeout, 30)).toBe("30 s");
    expect(displayValue(field({ name: "flips", kind: "int" }), 100000)).toBe("100,000");
  });
});

describe("edges", () => {
  it("parses, dedupes and toggles", () => {
    const { edges, errors } = parseEdges("2-1, 1-2\n3 4, 5-5, x");
    expect(edges).toEqual([
      [1, 2],
      [3, 4],
    ]);
    expect(errors).toHaveLength(2);
    expect(formatEdges(toggleEdge(edges, 4, 3))).toBe("1-2");
    expect(formatEdges(toggleEdge(edges, 2, 5))).toBe("1-2, 2-5, 3-4");
  });
});

describe("sudoku helpers", () => {
  it("only ever picks a valid board size", () => {
    expect(sudokuSize(16)).toBe(16);
    expect(sudokuSize("4")).toBe(4);
    expect(sudokuSize("4, 9, 16")).toBe(4);
    expect(sudokuSize(["16", "25"])).toBe(16);
    for (const odd of [3, "5", "", null, undefined, "4..9", "abc"]) expect(sudokuSize(odd)).toBe(9);
  });

  it("finds conflicts without crashing on boards that are not square sizes", () => {
    expect(() => conflictCells([[1, 1, 0], [0, 0, 0], [0, 0, 0]])).not.toThrow();
    expect(conflictCells([[1, 1, 0], [0, 0, 0], [0, 0, 0]])).toEqual(new Set(["0,0", "0,1"]));
  });

  it("parses pasted puzzles and finds conflicts", () => {
    const grid = parsePuzzle("1..4\n.4..\n..2.\n3..1")!;
    expect(grid[0]).toEqual([1, 0, 0, 4]);
    expect(parsePuzzle("123")).toBeNull();
    grid[0][1] = 1;
    expect(conflictCells(grid)).toEqual(new Set(["0,0", "0,1"]));
  });
});

function row(partial: Partial<BenchmarkRow>): BenchmarkRow {
  return {
    index: 0,
    case_index: 0,
    problem: "random_3sat",
    case_label: "",
    params: {},
    repeat: 1,
    solver: "cdcl",
    solver_label: "CDCL",
    status: "SAT",
    elapsed: 1,
    variables: 10,
    clauses: 40,
    size_variables: 10,
    expected: null,
    verified: true,
    check_errors: [],
    stats: {},
    timeout: 30,
    rule: null,
    error: null,
    decoded: null,
    ...partial,
  };
}

describe("stats", () => {
  const rows = [
    row({ params: { ratio: 3, n: 20 }, elapsed: 1 }),
    row({ params: { ratio: 3, n: 20 }, elapsed: 3 }),
    row({ params: { ratio: 4, n: 20 }, elapsed: 5, status: "UNSAT" }),
    row({ params: { ratio: 4, n: 20 }, elapsed: 0, status: "SKIPPED" }),
    row({ params: { ratio: 4, n: 20 }, solver_label: "DPLL", elapsed: 9 }),
  ];

  it("aggregates", () => {
    expect(aggregate([3, 1, 2], "median")).toBe(2);
    expect(aggregate([1, 2, 3, 4], "median")).toBe(2.5);
    expect(aggregate([1, 3], "mean")).toBe(2);
    expect(aggregate([], "max")).toBeNull();
  });

  it("finds the parameters that vary", () => {
    expect(varyingParams(rows).map((item) => item.name)).toEqual(["ratio"]);
  });

  it("groups series by x and ignores unmeasured runs", () => {
    const data = seriesByX(rows, (item) => item.params.ratio, (item) => item.solver_label, "elapsed", "median");
    expect(data.series).toEqual(["CDCL", "DPLL"]);
    expect(data.xs).toEqual([3, 4]);
    expect(data.points.get("CDCL")!.map((point) => point.value)).toEqual([2, 5]);
    expect(data.points.get("DPLL")!.map((point) => point.value)).toEqual([null, 9]);
  });

  it("computes status shares and flags suspicious answers", () => {
    const shares = statusShares(rows, (item) => item.params.ratio);
    expect(shares[1]).toEqual({ x: 4, total: 3, counts: { UNSAT: 1, SKIPPED: 1, SAT: 1 } });
    const flagged = suspiciousRows([row({ expected: "SAT", status: "UNSAT" }), row({ verified: false }), row({})]);
    expect(flagged).toHaveLength(2);
  });

  it("offers time, then the catalog's chart statistics, as measures", () => {
    const stats = [statSpec({ key: "restarts", label: "Restarts" }), statSpec({ key: "stored_literals", label: "Stored literals", chart: true })];
    expect(chartMetrics(stats)).toEqual([
      { value: "elapsed", label: "Time" },
      { value: "stored_literals", label: "Stored literals" },
    ]);
    expect(metricValue(row({ stats: { stored_literals: 42 } }), "stored_literals")).toBe(42);
  });

  it("labels a measure the catalog no longer charts", () => {
    expect(metricOption([], "peak_memory")).toEqual({ value: "peak_memory", label: "Peak memory" });
  });

  it("formats durations", () => {
    expect(formatSeconds(0.0005)).toBe("500 µs");
    expect(formatSeconds(0.25)).toBe("250.0 ms");
    expect(formatSeconds(75)).toBe("1 min 15 s");
  });
});

describe("benchmark drafts", () => {
  const catalog = {
    problems: [{ key: "g", title: "G", fields: [MODE, P, EDGES], graph_based: true }],
    solvers: [{ key: "cdcl", title: "CDCL", fields: [field({ name: "restarts", kind: "bool", default: false })] }],
    defaults: { benchmark_timeout: 30, benchmark_rules: [] },
  } as unknown as Catalog;

  it("round-trips a request and drops hidden fields", () => {
    const draft = draftFromRequest(catalog, {
      problems: ["g"],
      segments: [{ mode: "gnp", p: "0.1, 0.2", edges: "1-2" }],
      solvers: [{ solver: "cdcl", options: { restarts: true } }],
      repeats: 2,
      timeout: null,
      rules: [{ solver: "dpll", action: "cap", min_variables: 200, seconds: 10 }],
      seed: 7,
      workers: 3,
    });
    const request = requestFromDraft(catalog, draft);
    expect(request.segments).toEqual([{ mode: ["gnp"], p: "0.1, 0.2" }]);
    expect(request.solvers).toEqual([{ solver: "cdcl", options: { restarts: true }, label: undefined }]);
    expect(request.timeout).toBeNull();
    expect(request.repeats).toBe(2);
    expect(request.seed).toBe(7);
    expect(request.workers).toBe(3);
    // Drafts stored before the setting existed run one case at a time.
    expect(requestFromDraft(catalog, { ...draft, workers: undefined as unknown as number }).workers).toBe(1);
  });
});

describe("links in the algorithm notes", () => {
  const topics = ["dpll", "cdcl", "walksat", "encodings"];
  it("maps repository-relative links to app routes or GitHub", () => {
    expect(learnLink("dpll.md", topics)).toEqual({ href: "/learn/dpll", internal: true });
    expect(learnLink("../visualisations/cdcl/index.html", topics).href).toBe("/visualisations/cdcl/");
    expect(learnLink("../guide/performance.md", topics).href).toBe("https://github.com/Aziyck/SATsolver/blob/main/docs/guide/performance.md");
    expect(learnLink("https://example.org/x", topics).href).toBe("https://example.org/x");
  });
});

/** Rows whose parameters take the given values, one row per value of the first and second list. */
function sweep(first: [string, unknown[]], second?: [string, unknown[]]): BenchmarkRow[] {
  const rows: BenchmarkRow[] = [];
  for (const a of first[1]) {
    for (const b of second ? second[1] : [undefined]) {
      rows.push(row({ params: { [first[0]]: a, ...(second ? { [second[0]]: b } : {}) } }));
    }
  }
  return rows;
}

describe("default chart axes", () => {
  it("uses the case as the axis when no parameter varies", () => {
    expect(defaultAxes(varyingParams(sweep(["ratio", [4]])))).toEqual({ x: CASE_X, facet: null });
  });

  it("uses the one swept parameter as the axis and splits nothing", () => {
    expect(defaultAxes(varyingParams(sweep(["ratio", [3, 4, 5]])))).toEqual({ x: "ratio", facet: null });
  });

  it("prefers the first known axis name and splits by the other parameter", () => {
    const varying = varyingParams(sweep(["nodes", [10, 20]], ["ratio", [3, 4]]));
    expect(defaultAxes(varying)).toEqual({ x: "ratio", facet: "nodes" });
  });

  it("splits by problem when the problem varies", () => {
    const varying = varyingParams(sweep(["ratio", [3, 4]], ["problem", ["random_3sat", "clique"]]));
    expect(defaultAxes(varying)).toEqual({ x: "ratio", facet: "problem" });
  });

  it("has no split when only the problem varies", () => {
    expect(defaultAxes(varyingParams(sweep(["problem", ["random_3sat", "clique"]])))).toEqual({ x: "problem", facet: null });
  });

  it("falls back to a text parameter as the axis", () => {
    expect(defaultAxes(varyingParams(sweep(["mode", ["random", "planted"]])))).toEqual({ x: "mode", facet: null });
  });

  it("never splits by the seed or by a parameter with more than six values", () => {
    expect(defaultAxes(varyingParams(sweep(["ratio", [3, 4]], ["seed", [1, 2]])))).toEqual({ x: "ratio", facet: null });
    expect(defaultAxes(varyingParams(sweep(["ratio", [3, 4]], ["colors", [1, 2, 3, 4, 5, 6, 7]])))).toEqual({ x: "ratio", facet: null });
  });
});

describe("sorting runs", () => {
  const rows = [
    row({ index: 0, case_label: "n=10", elapsed: 5, stats: { conflicts: 30 } }),
    row({ index: 1, case_label: "n=2", elapsed: 1, stats: {} }),
    row({ index: 2, case_label: "n=100", elapsed: 3, stats: { conflicts: 7 } }),
  ];
  const order = (key: string, desc: boolean) => sortRows(rows, key, desc).map((item) => item.index);

  it("sorts by a built-in column, in both directions", () => {
    expect(order("elapsed", false)).toEqual([1, 2, 0]);
    expect(order("elapsed", true)).toEqual([0, 2, 1]);
    expect(order("index", true)).toEqual([2, 1, 0]);
  });

  it("sorts text with the numbers in it as numbers", () => {
    expect(order("case_label", false)).toEqual([1, 0, 2]);
  });

  it("sorts by a statistic and puts a run that lacks it first, then last when descending", () => {
    expect(sortValue(rows[1], "conflicts")).toBe(-1);
    expect(order("conflicts", false)).toEqual([1, 2, 0]);
    expect(order("conflicts", true)).toEqual([0, 2, 1]);
  });

  it("does not change the list it is given", () => {
    const before = rows.map((item) => item.index);
    sortRows(rows, "elapsed", true);
    expect(rows.map((item) => item.index)).toEqual(before);
  });
});

describe("filtering runs", () => {
  const rows = [
    row({ index: 0, case_label: "n=10 ratio=3", status: "SAT", solver_label: "CDCL" }),
    row({ index: 1, case_label: "n=10 ratio=5", status: "UNSAT", solver_label: "DPLL" }),
    row({ index: 2, case_label: "N=20 ratio=3", status: "TIMEOUT", solver_label: "CDCL" }),
    row({ index: 3, case_label: "n=20 ratio=5", status: "SAT", solver_label: "DPLL", verified: false }),
  ];
  const none: RowFilter = { statuses: [], solvers: [], query: "", onlySuspicious: false };
  const kept = (filter: Partial<RowFilter>) => filterRows(rows, { ...none, ...filter }).map((item) => item.index);

  it("keeps every run when no filter is set", () => {
    expect(kept({})).toEqual([0, 1, 2, 3]);
  });

  it("filters by status, by solver and by the text of the case, ignoring case", () => {
    expect(kept({ statuses: ["SAT", "TIMEOUT"] })).toEqual([0, 2, 3]);
    expect(kept({ solvers: ["DPLL"] })).toEqual([1, 3]);
    expect(kept({ query: "n=20" })).toEqual([2, 3]);
  });

  it("keeps only suspicious runs on request", () => {
    expect(kept({ onlySuspicious: true })).toEqual([3]);
  });

  it("combines the filters", () => {
    expect(kept({ statuses: ["SAT"], solvers: ["DPLL"], query: "ratio=5" })).toEqual([3]);
    expect(kept({ statuses: ["UNSAT"], onlySuspicious: true })).toEqual([]);
  });
});
