// Types mirroring the JSON returned by the Python API (sat_web/api.py).

export type FieldKind = "int" | "float" | "bool" | "choice" | "text" | "seed" | "edges" | "sudoku_grid" | "cnf";

export interface Choice {
  value: string;
  label: string;
  help: string;
}

export interface Field {
  name: string;
  label: string;
  kind: FieldKind;
  default: unknown;
  help: string;
  min: number | null;
  max: number | null;
  step: number | null;
  choices: Choice[];
  optional: boolean;
  sweepable: boolean;
  group: string;
  show_if: Record<string, unknown[]>;
  placeholder: string;
  unit: string;
  advanced: boolean;
  short: string;
}

export type ResultView = "sudoku" | "queens" | "graph" | "assignment";

export interface ProblemSpec {
  key: string;
  title: string;
  summary: string;
  description: string;
  category: string;
  image: string | null;
  result_view: ResultView;
  graph_based: boolean;
  fields: Field[];
}

export interface SolverSpec {
  key: string;
  title: string;
  complete: boolean;
  summary: string;
  description: string;
  fields: Field[];
}

export interface Rule {
  solver: string;
  action: "cap" | "skip";
  min_variables: number;
  seconds: number | null;
}

export interface SolverEntry {
  solver: string;
  options?: Record<string, unknown>;
  label?: string;
}

export interface BenchmarkRequest {
  problems: string[];
  segments: Record<string, unknown>[];
  solvers: SolverEntry[];
  repeats: number;
  timeout: number | null;
  rules: Rule[];
  log_level?: string;
  seed?: number | string | null;
  title?: string;
}

export interface Preset {
  key: string;
  title: string;
  description: string;
  tags: string[];
  request: BenchmarkRequest;
  cases: number;
  runs: number;
  rules: string[];
}

export interface Catalog {
  version: string;
  problems: ProblemSpec[];
  solvers: SolverSpec[];
  presets: Preset[];
  log_levels: string[];
  limits: { max_clauses: number; max_benchmark_runs: number };
  defaults: { solve_timeout: number; benchmark_timeout: number; benchmark_rules: Rule[] };
}

export type JobKind = "solve" | "generate" | "benchmark";
export type JobStatus = "queued" | "running" | "cancelling" | "done" | "failed" | "cancelled" | "interrupted";
export type RunStatus = "SAT" | "UNSAT" | "UNKNOWN" | "TIMEOUT" | "CANCELLED" | "SKIPPED" | "ERROR";

export interface Progress {
  current: number | null;
  total: number | null;
  message: string;
}

export interface JobSummary {
  id: number;
  /** Increases with every published update; lets the client ignore stale copies. */
  rev: number;
  label: string;
  kind: JobKind;
  title: string;
  status: JobStatus;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  progress: Progress;
  row_count: number;
  problems: string[];
  solver: string | null;
  result_status: RunStatus | null;
  verified: boolean | null;
  elapsed: number | null;
  error: string | null;
}

export interface Fact {
  label: string;
  value: string | number;
  hint?: string;
}

export interface Estimate {
  variables: number;
  clauses: number;
}

export interface InstanceInfo {
  name: string;
  problem: string;
  params: Record<string, unknown>;
  variables: number;
  clauses: number;
  size_variables: number;
  max_variable: number;
  facts: Fact[];
  visual: any;
  expected: RunStatus | null;
  encode_seconds: number;
  cnf_file: string | null;
}

export type Stats = Record<string, number | string | boolean | null>;

export interface SolveResult {
  solver: string;
  solver_label: string;
  options: Record<string, unknown>;
  options_summary: string;
  status: RunStatus;
  elapsed: number;
  stats: Stats;
  decoded: any;
  verified: boolean | null;
  check_errors: string[];
  expected: RunStatus | null;
  timeout: number | null;
  error: string | null;
  model_file: string | null;
}

export type LogLine = [string, string];

export interface SolveRequest {
  problem: string;
  params: Record<string, unknown>;
  solver?: string;
  options?: Record<string, unknown>;
  timeout?: number | null;
  log_level?: string;
}

export interface JobDetail extends JobSummary {
  request: SolveRequest & BenchmarkRequest;
  instance: InstanceInfo | null;
  result: SolveResult | null;
  errors: Record<string, string> | null;
  logs: LogLine[];
  log_count: number;
}

export interface BenchmarkRow {
  index: number;
  case_index: number;
  problem: string;
  case_label: string;
  params: Record<string, unknown>;
  repeat: number;
  solver: string;
  solver_label: string;
  status: RunStatus;
  elapsed: number;
  variables: number;
  clauses: number;
  size_variables: number;
  expected: RunStatus | null;
  verified: boolean | null;
  check_errors: string[];
  stats: Stats;
  timeout: number | null;
  rule: string | null;
  error: string | null;
  decoded: any;
  run_label?: string;
}

export interface PlanSummary {
  cases: number;
  runs: number;
  solvers: string[];
  rules: string[];
  largest: Estimate | null;
  total_clauses: number | null;
  sample: { problem: string; label: string; repeat: number; estimate: Estimate | null }[];
  seed: number;
}

export interface PreviewResponse {
  label: string;
  estimate: Estimate | null;
  too_large: boolean;
  preview: any;
}

export interface RowCase {
  row: BenchmarkRow;
  problem: string;
  params: Record<string, unknown>;
  instance: InstanceInfo;
}

export type LiveEvent =
  | { type: "job"; job: JobSummary }
  | { type: "log"; job_id: number; line: LogLine; synthetic?: boolean }
  | { type: "instance"; job_id: number; instance: InstanceInfo }
  | { type: "result"; job_id: number; result: SolveResult }
  | { type: "row"; job_id: number; row: BenchmarkRow }
  | { type: "deleted"; job_id: number }
  | { type: "resync" };

export type ServerMessage =
  | { type: "hello"; version: string; jobs: JobSummary[] }
  | { type: "batch"; events: LiveEvent[] };
