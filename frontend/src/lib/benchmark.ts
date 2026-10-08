import type { BenchmarkRequest, Catalog, Field, Rule } from "../api/types";
import { cloneValue, defaultValues, isNumericKind, type Values } from "./params";

export interface SolverDraft {
  id: number;
  solver: string;
  options: Values;
  label: string;
}

export interface BenchmarkDraft {
  title: string;
  problems: string[];
  segments: Values[];
  solvers: SolverDraft[];
  repeats: number | string;
  timeout: number | string;
  seed: number | string;
  logLevel: string;
  rules: Rule[];
  /** Cases solved at the same time; 1 runs them one after another. */
  workers: number | string;
}

let nextId = 1;
export function newId(): number {
  nextId += 1;
  return Date.now() * 100 + nextId;
}

/** Fields of all selected problems, deduplicated by name (graph problems share their graph fields). */
export function unionFields(catalog: Catalog, problems: string[]): Field[] {
  const seen = new Map<string, Field>();
  for (const key of problems) {
    const spec = catalog.problems.find((problem) => problem.key === key);
    for (const field of spec?.fields ?? []) {
      if (!seen.has(field.name)) seen.set(field.name, field);
    }
  }
  return [...seen.values()];
}

/** Benchmark-form value for a field: sweepable numbers are edited as text, sweepable choices as lists. */
export function sweepValue(field: Field, value: unknown): unknown {
  if (field.sweepable && field.kind === "choice") {
    if (Array.isArray(value)) return value.map(String);
    return String(value ?? field.default)
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }
  if (field.sweepable && field.kind === "cnf") return Array.isArray(value) ? value : [value];
  if (field.sweepable && isNumericKind(field)) {
    if (Array.isArray(value)) return value.join(", ");
    return value === null || value === undefined ? "" : String(value);
  }
  return cloneValue(value);
}

export function sweepDefaults(fields: Field[]): Values {
  return Object.fromEntries(fields.map((field) => [field.name, sweepValue(field, field.default)]));
}

/** show_if check that accepts lists (a swept choice shows a field if any selected value allows it). */
export function isVisibleSweep(field: Field, values: Values): boolean {
  return Object.entries(field.show_if).every(([other, allowed]) => {
    const value = values[other];
    return Array.isArray(value) ? value.some((item) => allowed.includes(item)) : allowed.includes(value as never);
  });
}

export function emptyDraft(catalog: Catalog, problem = "random_3sat"): BenchmarkDraft {
  const fields = unionFields(catalog, [problem]);
  return {
    title: "",
    problems: [problem],
    segments: [sweepDefaults(fields)],
    solvers: [{ id: newId(), solver: "cdcl", options: defaultValues(catalog.solvers.find((s) => s.key === "cdcl")?.fields ?? []), label: "" }],
    repeats: 1,
    timeout: catalog.defaults.benchmark_timeout,
    seed: 1,
    logLevel: "normal",
    rules: catalog.defaults.benchmark_rules.map((rule) => ({ ...rule })),
    workers: 1,
  };
}

/** Turn a stored request (a preset or a past job) into an editable draft. */
export function draftFromRequest(catalog: Catalog, request: BenchmarkRequest): BenchmarkDraft {
  const problems = request.problems?.length ? request.problems : ["random_3sat"];
  const fields = unionFields(catalog, problems);
  const segments = (request.segments?.length ? request.segments : [{}]).map((segment) => {
    const values = sweepDefaults(fields);
    for (const [name, value] of Object.entries(segment)) {
      const field = fields.find((item) => item.name === name);
      if (field) values[name] = sweepValue(field, value);
    }
    return values;
  });
  return {
    title: request.title ?? "",
    problems,
    segments,
    solvers: (request.solvers ?? []).map((entry) => {
      const spec = catalog.solvers.find((solver) => solver.key === entry.solver);
      return {
        id: newId(),
        solver: entry.solver,
        options: { ...defaultValues(spec?.fields ?? []), ...(entry.options ?? {}) },
        label: entry.label ?? "",
      };
    }),
    repeats: request.repeats ?? 1,
    timeout: request.timeout ?? "",
    seed: request.seed ?? "",
    logLevel: request.log_level ?? "normal",
    rules: (request.rules ?? []).map((rule) => ({ ...rule })),
    workers: request.workers ?? 1,
  };
}

export function requestFromDraft(catalog: Catalog, draft: BenchmarkDraft): BenchmarkRequest {
  const fields = unionFields(catalog, draft.problems);
  return {
    title: draft.title || undefined,
    problems: draft.problems,
    segments: draft.segments.map((values) =>
      Object.fromEntries(fields.filter((field) => isVisibleSweep(field, values)).map((field) => [field.name, values[field.name]])),
    ),
    solvers: draft.solvers.map((entry) => {
      const spec = catalog.solvers.find((solver) => solver.key === entry.solver);
      const options = Object.fromEntries((spec?.fields ?? []).map((field) => [field.name, entry.options[field.name]]));
      return { solver: entry.solver, options, label: entry.label.trim() || undefined };
    }),
    repeats: Number(draft.repeats) || 1,
    timeout: draft.timeout === "" || draft.timeout === null ? null : Number(draft.timeout),
    rules: draft.rules,
    log_level: draft.logLevel,
    seed: draft.seed === "" ? null : draft.seed,
    // Drafts saved before this setting existed have no workers value.
    workers: Number(draft.workers ?? 1) || 1,
  };
}
