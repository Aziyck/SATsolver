import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderWithApp } from "../test/render";
import { StatsTable } from "./SolverSettingsTable";

describe("StatsTable", () => {
  it("shows a readable label for each statistic", () => {
    renderWithApp(<StatsTable stats={{ decisions: 12, conflicts: 3 }} />);
    expect(screen.getByText("Decisions")).toBeTruthy();
    expect(screen.getByText("Conflicts")).toBeTruthy();
  });
});
