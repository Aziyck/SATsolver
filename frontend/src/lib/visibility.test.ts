import { describe, expect, it } from "vitest";
import shared from "../../../tests/fixtures/show_if_cases.json";
import type { Field } from "../api/types";
import { field } from "../test/fields";
import { isVisibleSweep } from "./benchmark";
import { isVisible, type Values } from "./params";

// The same cases run on the server in tests/test_show_if_agreement.py: both sides must name the same visible fields.
type FieldJson = Partial<Field> & Pick<Field, "name" | "kind">;
const fields = (shared.fields as unknown as FieldJson[]).map((item) => field(item));

describe("show_if agrees with the server", () => {
  it.each(shared.single)("single values: $name", (entry) => {
    const visible = fields.filter((item) => isVisible(item, entry.values as Values)).map((item) => item.name);
    expect(visible).toEqual(entry.visible);
  });

  it.each(shared.sweep)("sweeps: $name", (entry) => {
    const visible = fields.filter((item) => isVisibleSweep(item, entry.values as Values)).map((item) => item.name);
    expect(visible).toEqual(entry.visible);
  });
});
