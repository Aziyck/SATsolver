import type { BenchmarkRow } from "../api/types";

export type Aggregate = "median" | "mean" | "min" | "max";
export type Metric = "elapsed" | "decisions" | "conflicts" | "propagations" | "learned_clauses" | "flips";

export const METRICS: { value: Metric; label: string; unit?: string }[] = [
  { value: "elapsed", label: "Time", unit: "s" },
  { value: "decisions", label: "Decisions" },
  { value: "conflicts", label: "Conflicts" },
  { value: "propagations", label: "Propagations" },
  { value: "learned_clauses", label: "Learned clauses" },
  { value: "flips", label: "Flips" },
];

/** Statuses that produced a measurement (skipped, cancelled and failed runs did not). */
export const MEASURED = new Set(["SAT", "UNSAT", "UNKNOWN", "TIMEOUT"]);

export function metricValue(row: BenchmarkRow, metric: Metric): number | null {
  if (!MEASURED.has(row.status)) return null;
  if (metric === "elapsed") return row.elapsed;
  const value = row.stats[metric];
  return typeof value === "number" ? value : null;
}

export function aggregate(values: number[], how: Aggregate): number | null {
  if (!values.length) return null;
  const sorted = [...values].sort((a, b) => a - b);
  switch (how) {
    case "min":
      return sorted[0];
    case "max":
      return sorted[sorted.length - 1];
    case "mean":
      return sorted.reduce((sum, value) => sum + value, 0) / sorted.length;
    case "median": {
      const middle = Math.floor(sorted.length / 2);
      return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2;
    }
  }
}

/** Parameters whose value differs between rows (candidates for chart axes). */
export function varyingParams(rows: BenchmarkRow[]): { name: string; numeric: boolean; values: unknown[] }[] {
  const seen = new Map<string, Map<string, unknown>>();
  for (const row of rows) {
    for (const [name, value] of Object.entries(row.params)) {
      if (value !== null && typeof value === "object") continue;
      const values = seen.get(name) ?? new Map<string, unknown>();
      values.set(JSON.stringify(value), value);
      seen.set(name, values);
    }
  }
  const result = [];
  for (const [name, values] of seen) {
    const list = [...values.values()];
    if (list.length > 1) {
      result.push({ name, numeric: list.every((value) => typeof value === "number"), values: list });
    }
  }
  return result;
}

export function sortValues(values: unknown[]): unknown[] {
  return [...values].sort((a, b) =>
    typeof a === "number" && typeof b === "number" ? a - b : String(a).localeCompare(String(b), undefined, { numeric: true }),
  );
}

export interface SeriesPoint {
  x: unknown;
  value: number | null;
  count: number;
}

/** Group rows by series key and x value, and aggregate the metric. */
export function seriesByX(
  rows: BenchmarkRow[],
  xOf: (row: BenchmarkRow) => unknown,
  seriesOf: (row: BenchmarkRow) => string,
  metric: Metric,
  how: Aggregate,
): { series: string[]; xs: unknown[]; points: Map<string, SeriesPoint[]> } {
  const series: string[] = [];
  const xsMap = new Map<string, unknown>();
  const buckets = new Map<string, Map<string, number[]>>();
  for (const row of rows) {
    const key = seriesOf(row);
    if (!series.includes(key)) series.push(key);
    const x = xOf(row);
    const xKey = JSON.stringify(x);
    xsMap.set(xKey, x);
    const value = metricValue(row, metric);
    const byX = buckets.get(key) ?? new Map<string, number[]>();
    const values = byX.get(xKey) ?? [];
    if (value !== null) values.push(value);
    byX.set(xKey, values);
    buckets.set(key, byX);
  }
  const xs = sortValues([...xsMap.values()]);
  const points = new Map<string, SeriesPoint[]>();
  for (const key of series) {
    const byX = buckets.get(key) ?? new Map<string, number[]>();
    points.set(
      key,
      xs.map((x) => {
        const values = byX.get(JSON.stringify(x)) ?? [];
        return { x, value: aggregate(values, how), count: values.length };
      }),
    );
  }
  return { series, xs, points };
}

/** Share of each status per x value (for one solver or all). */
export function statusShares(rows: BenchmarkRow[], xOf: (row: BenchmarkRow) => unknown) {
  const xsMap = new Map<string, unknown>();
  const counts = new Map<string, Map<string, number>>();
  for (const row of rows) {
    const x = xOf(row);
    const key = JSON.stringify(x);
    xsMap.set(key, x);
    const byStatus = counts.get(key) ?? new Map<string, number>();
    byStatus.set(row.status, (byStatus.get(row.status) ?? 0) + 1);
    counts.set(key, byStatus);
  }
  const xs = sortValues([...xsMap.values()]);
  return xs.map((x) => {
    const byStatus = counts.get(JSON.stringify(x)) ?? new Map<string, number>();
    const total = [...byStatus.values()].reduce((sum, count) => sum + count, 0);
    return { x, total, counts: Object.fromEntries(byStatus) as Record<string, number> };
  });
}

export function statusCounts(rows: BenchmarkRow[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const row of rows) counts[row.status] = (counts[row.status] ?? 0) + 1;
  return counts;
}

/** Runs whose answer contradicts a generator guarantee, or whose model failed verification. */
export function suspiciousRows(rows: BenchmarkRow[]): BenchmarkRow[] {
  return rows.filter(
    (row) =>
      row.verified === false ||
      (row.expected !== null && (row.status === "SAT" || row.status === "UNSAT") && row.status !== row.expected),
  );
}
