import type { Catalog, StatSpec } from "../api/types";

/** A statistic as the API sends it, with every property not given left at its empty value. */
export function statSpec(partial: Partial<StatSpec> & Pick<StatSpec, "key">): StatSpec {
  return { label: partial.key, short: "", help: "", unit: "", csv: false, chart: false, ...partial };
}

/** The catalog as GET /api/catalog sends it, with only what a test names filled in. */
export function catalog(partial: Partial<Catalog> = {}): Catalog {
  return {
    version: "test",
    problems: [],
    solvers: [],
    stats: [],
    presets: [],
    log_levels: ["normal"],
    limits: { max_clauses: 1, max_benchmark_runs: 1, max_workers: 1 },
    defaults: { solve_timeout: 1, benchmark_timeout: 1, benchmark_rules: [] },
    ...partial,
  };
}
