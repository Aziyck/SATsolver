import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { RunEnvironment, SolverSpec } from "../api/types";
import { catalog, statSpec } from "../test/catalog";
import { field } from "../test/fields";
import { renderWithApp } from "../test/render";
import { MachineBlock, SolverSettingsTable, StatsTable } from "./SolverSettingsTable";

const ENVIRONMENT: RunEnvironment = {
  python_implementation: "CPython",
  python_version: "3.12.0",
  os: "Linux 6.8.0 (x86_64)",
  cpu_model: "AMD Ryzen 7 4800H",
  cpu_logical_cores: 16,
  cpu_physical_cores: 8,
  ram_total_gb: 15.4,
  wizsat_version: "2.0.0",
  git_commit: "75c0c05",
  git_dirty: false,
};

describe("MachineBlock", () => {
  it("shows the interpreter, the CPU, the cores, the memory and the commit of a job that has them", () => {
    renderWithApp(<MachineBlock environment={ENVIRONMENT} />);
    expect(screen.getByText("Machine")).toBeTruthy();
    expect(screen.getByText("CPython 3.12.0")).toBeTruthy();
    expect(screen.getByText("AMD Ryzen 7 4800H")).toBeTruthy();
    expect(screen.getByText("8 physical, 16 logical")).toBeTruthy();
    expect(screen.getByText("15.4 GB")).toBeTruthy();
    expect(screen.getByText("2.0.0, commit 75c0c05")).toBeTruthy();
    expect(screen.queryByText("not recorded")).toBeNull();
  });

  it("says not recorded for a job without an environment", () => {
    renderWithApp(<MachineBlock environment={null} />);
    expect(screen.getByText("Machine")).toBeTruthy();
    expect(screen.getByText(/not recorded/)).toBeTruthy();
    expect(screen.queryByText("Processor")).toBeNull();
  });
});

// Modelled on the CDCL and ProbSAT options in sat_core/solver_registry.py, trimmed to
// what these tests need (no advanced flags or bounds).
const CDCL: SolverSpec = {
  key: "cdcl",
  title: "CDCL",
  complete: true,
  summary: "Conflict-driven clause learning.",
  description: "",
  fields: [
    field({ name: "restarts", label: "Restarts", kind: "bool", default: true }),
    field({
      name: "restart_strategy",
      label: "Restart schedule",
      kind: "choice",
      default: "luby",
      choices: [
        { value: "luby", label: "Luby", help: "" },
        { value: "fixed", label: "Fixed", help: "" },
      ],
      show_if: { restarts: [true] },
    }),
    field({ name: "restart_interval", label: "Restart interval", kind: "int", default: 100, unit: "conflicts", show_if: { restarts: [true] } }),
    field({ name: "clause_deletion", label: "Clean up learned clauses", kind: "bool", default: true }),
    field({
      name: "learned_limit",
      label: "Learned clause limit",
      kind: "int",
      default: null,
      optional: true,
      placeholder: "automatic",
      show_if: { clause_deletion: [true] },
    }),
  ],
};

const PROBSAT: SolverSpec = {
  key: "probsat",
  title: "ProbSAT",
  complete: false,
  summary: "Probabilistic local search.",
  description: "",
  fields: [
    field({ name: "max_tries", label: "Max tries", kind: "int", default: 10 }),
    field({ name: "cb", label: "Break exponent cb", kind: "float", default: null, optional: true, placeholder: "automatic" }),
  ],
};

function row(label: string): HTMLElement {
  const cell = screen.getByText(label);
  const tr = cell.closest("tr");
  if (!tr) throw new Error(`no table row for ${label}`);
  return tr;
}

describe("SolverSettingsTable", () => {
  it("marks a changed option and shows its default next to it", () => {
    renderWithApp(<SolverSettingsTable spec={CDCL} options={{ restart_interval: 50 }} />);
    const changed = within(row("Restart interval"));
    expect(changed.getByText("50 conflicts")).toBeTruthy();
    expect(changed.getByText("changed")).toBeTruthy();
    expect(changed.getByText("100 conflicts")).toBeTruthy();
    expect(within(row("Restarts")).queryByText("changed")).toBeNull();
    expect(screen.getByText(/1 of 5 options changed from the default/)).toBeTruthy();
  });

  it("leaves out options that another option switched off", () => {
    renderWithApp(<SolverSettingsTable spec={CDCL} options={{ restarts: false }} />);
    expect(screen.getByText("Restarts")).toBeTruthy();
    expect(screen.queryByText("Restart schedule")).toBeNull();
    expect(screen.queryByText("Restart interval")).toBeNull();
  });

  it("lists an option the solver no longer has as no longer an option", () => {
    renderWithApp(<SolverSettingsTable spec={PROBSAT} options={{ noise: 0.5 }} />);
    expect(screen.getByText(/not an option of ProbSAT \(any more\): noise=0\.5/)).toBeTruthy();
    expect(screen.queryByRole("cell", { name: /noise/i })).toBeNull();
  });

  it("shows the placeholder for a blank optional value", () => {
    renderWithApp(<SolverSettingsTable spec={CDCL} options={{ learned_limit: null }} />);
    const [, used] = within(row("Learned clause limit")).getAllByRole("cell");
    expect(used.textContent).toBe("automatic");
  });
});

describe("StatsTable", () => {
  const STATS = catalog({
    stats: [
      statSpec({ key: "decisions", label: "Decisions", help: "Times the solver guessed a value." }),
      statSpec({ key: "elapsed", label: "Solver time", unit: "s" }),
      statSpec({ key: "glue_bonus_count", label: "Glue bonus", help: "Made-up statistic only the catalog knows." }),
    ],
  });

  it("takes the label of each statistic from the catalog", () => {
    renderWithApp(<StatsTable stats={{ decisions: 12, glue_bonus_count: 3 }} />, { queryData: [[["catalog"], STATS]] });
    expect(screen.getByText("Decisions")).toBeTruthy();
    expect(screen.getByText("Glue bonus")).toBeTruthy();
  });

  it("shows elapsed as a time", () => {
    renderWithApp(<StatsTable stats={{ elapsed: 0.0123 }} />, { queryData: [[["catalog"], STATS]] });
    expect(within(row("Solver time")).getByText("12.3 ms")).toBeTruthy();
  });

  it("gives a key the catalog lacks a readable label", () => {
    renderWithApp(<StatsTable stats={{ glue_bonus_count: 1234 }} />, { queryData: [[["catalog"], catalog()]] });
    expect(within(row("Glue bonus count")).getByText("1,234")).toBeTruthy();
  });
});
