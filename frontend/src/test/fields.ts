import type { Field } from "../api/types";

/** A parameter field as the API sends it, with every property not given left at its empty value. */
export function field(partial: Partial<Field> & Pick<Field, "name" | "kind">): Field {
  return {
    label: partial.name,
    default: null,
    help: "",
    min: null,
    max: null,
    step: null,
    choices: [],
    optional: false,
    sweepable: false,
    group: "",
    show_if: {},
    placeholder: "",
    unit: "",
    advanced: false,
    short: "",
    ...partial,
  };
}
