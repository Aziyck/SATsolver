import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SolverSpec } from "../api/types";
import { field } from "../test/fields";
import { renderWithApp } from "../test/render";
import { SolverSettingsTable, StatsTable } from "./SolverSettingsTable";

// Trimmed copies of the CDCL and ProbSAT option lists in sat_core/solver_registry.py.
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
    expect(screen.queryByRole("cell", { name: /^Noise/ })).toBeNull();
  });

  it("shows the placeholder for a blank optional value", () => {
    renderWithApp(<SolverSettingsTable spec={CDCL} options={{ learned_limit: null }} />);
    const [used, byDefault] = within(row("Learned clause limit")).getAllByText("automatic");
    expect(used).toBeTruthy();
    expect(byDefault).toBeTruthy();
    expect(within(row("Learned clause limit")).queryByText("none")).toBeNull();
  });
});

describe("StatsTable", () => {
  it("shows a readable label for each statistic", () => {
    renderWithApp(<StatsTable stats={{ decisions: 12, conflicts: 3 }} />);
    expect(screen.getByText("Decisions")).toBeTruthy();
    expect(screen.getByText("Conflicts")).toBeTruthy();
  });

  it("shows elapsed as a time and gives unknown keys a readable label", () => {
    renderWithApp(<StatsTable stats={{ elapsed: 0.0123, glue_bonus_count: 1234 }} />);
    expect(within(row("Solver time")).getByText("12.3 ms")).toBeTruthy();
    expect(within(row("Glue bonus count")).getByText("1,234")).toBeTruthy();
  });
});
