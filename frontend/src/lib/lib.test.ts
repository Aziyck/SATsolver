import { describe, expect, it } from "vitest";
import type { BenchmarkRow, Catalog, Field } from "../api/types";
import { draftFromRequest, isVisibleSweep, requestFromDraft, sweepValue } from "./benchmark";
import { formatEdges, parseEdges, toggleEdge } from "./edges";
import { formatSeconds } from "./format";
import { defaultValues, isVisible, parseNumberList, visibleValues } from "./params";
import { aggregate, seriesByX, statusShares, suspiciousRows, varyingParams } from "./stats";
import { learnLink } from "./learn";
import { conflictCells, parsePuzzle } from "./sudoku";

function field(partial: Partial<Field> & Pick<Field, "name" | "kind">): Field {
  return {
    label: partial.name,
    default: null,
    help: "",
    min: null,
    max: null,
    step: null,
    choices: [],
    optional: false,
    sweepable: false,
    group: "",
    show_if: {},
    placeholder: "",
    unit: "",
    advanced: false,
    short: "",
    ...partial,
  };
}

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
