import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { catalog, statSpec } from "../../test/catalog";
import { renderWithApp } from "../../test/render";
import { MeasureSelect } from "./MeasureSelect";

const CATALOG = catalog({
  stats: [
    statSpec({ key: "decisions", label: "Decisions", chart: true }),
    statSpec({ key: "restarts", label: "Restarts" }),
    // Made up: the picker must offer it because the catalog says chart, not because the frontend lists it.
    statSpec({ key: "stored_literals", label: "Stored literals", chart: true }),
  ],
});

function openPicker() {
  renderWithApp(<MeasureSelect value="elapsed" onChange={() => {}} />, { queryData: [[["catalog"], CATALOG]] });
  fireEvent.click(screen.getByRole("textbox", { name: "Measure" }));
  return screen.getAllByRole("option").map((option) => option.textContent);
}

describe("MeasureSelect", () => {
  it("offers time first, then every statistic the catalog marks for charts", () => {
    expect(openPicker()).toEqual(["Time", "Decisions", "Stored literals"]);
  });

  it("leaves out a statistic the catalog does not mark for charts", () => {
    expect(openPicker()).not.toContain("Restarts");
  });
});
