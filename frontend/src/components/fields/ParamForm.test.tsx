import { fireEvent, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import type { Field } from "../../api/types";
import { defaultValues, type Values } from "../../lib/params";
import { field } from "../../test/fields";
import { renderWithApp } from "../../test/render";
import { CompactHelp, ParamForm, ResetToDefaults } from "./ParamForm";

const FIELDS: Field[] = [
  field({ name: "restarts", label: "Restarts", kind: "bool", default: true, help: "Start again now and then." }),
  field({ name: "restart_interval", label: "Restart interval", kind: "int", default: 100, unit: "conflicts", show_if: { restarts: [true] } }),
  field({ name: "max_tries", label: "Max tries", kind: "int", default: 10, help: "Random restarts per run." }),
  field({ name: "noise", label: "Noise", kind: "float", default: 0.5 }),
  field({
    name: "branching",
    label: "Branching",
    kind: "choice",
    default: "vsids",
    choices: [
      { value: "vsids", label: "VSIDS", help: "" },
      { value: "moms", label: "MOMS", help: "" },
    ],
  }),
  field({ name: "learned_limit", label: "Learned clause limit", kind: "int", default: null, optional: true, placeholder: "automatic", advanced: true }),
  field({ name: "random_seed", label: "Random seed", kind: "seed", default: null, optional: true, advanced: true }),
];

/** The form as a page uses it: values in state, per-field reset and "reset all". */
function Form({ initial = {}, compact = false }: { initial?: Values; compact?: boolean }) {
  const [values, setValues] = useState<Values>({ ...defaultValues(FIELDS), ...initial });
  const form = (
    <>
      <ResetToDefaults fields={FIELDS} values={values} onReset={() => setValues(defaultValues(FIELDS))} />
      <ParamForm fields={FIELDS} values={values} onChange={(name, value) => setValues((old) => ({ ...old, [name]: value }))} resettable />
    </>
  );
  return compact ? <CompactHelp.Provider value>{form}</CompactHelp.Provider> : form;
}

const input = (label: string) => screen.getByLabelText(label) as HTMLInputElement;
// Mantine puts a switch's description inside its label, so the accessible name starts with the label.
const restartsSwitch = () => screen.getByRole("switch", { name: /^Restarts/ });

describe("ParamForm", () => {
  it("gives a changed field a reset control that restores its default", () => {
    renderWithApp(<Form initial={{ max_tries: 25 }} />);
    expect(input("Max tries").value).toBe("25");
    expect(screen.queryByRole("button", { name: "Reset Noise to its default" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Reset Max tries to its default" }));

    expect(input("Max tries").value).toBe("10");
    expect(screen.queryByRole("button", { name: "Reset Max tries to its default" })).toBeNull();
  });

  it("resets every changed field with ResetToDefaults, which then disappears", () => {
    renderWithApp(<Form initial={{ max_tries: 25, noise: 0.25 }} />);

    fireEvent.click(screen.getByRole("button", { name: "Reset 2 changed options" }));

    expect(input("Max tries").value).toBe("10");
    expect(input("Noise").value).toBe("0.5");
    expect(screen.queryByRole("button", { name: /Reset \d+ changed option/ })).toBeNull();
  });

  it("says how many hidden advanced fields are changed", () => {
    renderWithApp(<Form initial={{ learned_limit: 5000 }} />);
    expect(screen.getByRole("button", { name: "Advanced options (2) - 1 changed" })).toBeTruthy();
  });

  it("shows a field with show_if only while the field it depends on allows it", () => {
    renderWithApp(<Form />);
    expect(input("Restart interval (conflicts)")).toBeTruthy();

    fireEvent.click(restartsSwitch());
    expect(screen.queryByLabelText("Restart interval (conflicts)")).toBeNull();

    fireEvent.click(restartsSwitch());
    expect(input("Restart interval (conflicts)")).toBeTruthy();
  });

  it("shows help as a line under the field", () => {
    renderWithApp(<Form />);
    expect(screen.getByText("Random restarts per run.")).toBeTruthy();
  });
});

describe("ParamForm inside CompactHelp", () => {
  it("keeps help out of the form and puts short numeric fields two per row", () => {
    renderWithApp(<Form compact />);
    expect(screen.queryByText("Random restarts per run.")).toBeNull();
    expect(screen.queryByText("Start again now and then.")).toBeNull();

    const row = (label: string) => input(label).closest(".mantine-SimpleGrid-root");
    expect(row("Max tries")).not.toBeNull();
    expect(row("Max tries")).toBe(row("Noise"));
    expect(screen.getByRole("radiogroup", { name: "Branching" }).closest(".mantine-SimpleGrid-root")).toBeNull();
  });
});
