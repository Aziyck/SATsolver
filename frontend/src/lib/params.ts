import type { Field } from "../api/types";

export type Values = Record<string, unknown>;

/** Default value of every field (the server applies the same defaults). */
export function defaultValues(fields: Field[]): Values {
  return Object.fromEntries(fields.map((field) => [field.name, cloneValue(field.default)]));
}

export function cloneValue<T>(value: T): T {
  return value === null || typeof value !== "object" ? value : (JSON.parse(JSON.stringify(value)) as T);
}

/** Mirrors ParamField.visible on the server: every show_if condition must hold. */
export function isVisible(field: Field, values: Values): boolean {
  return Object.entries(field.show_if).every(([other, allowed]) => allowed.includes(values[other] as never));
}

export function visibleFields(fields: Field[], values: Values): Field[] {
  return fields.filter((field) => isVisible(field, values));
}

/** Values of visible fields only, as sent to the server. */
export function visibleValues(fields: Field[], values: Values): Values {
  return Object.fromEntries(visibleFields(fields, values).map((field) => [field.name, values[field.name]]));
}

export function isNumericKind(field: Field): boolean {
  return field.kind === "int" || field.kind === "float" || field.kind === "seed";
}

/**
 * Parse "10, 20, 30", "1..20" or "0.1..0.5:0.1" like the server does.
 * Returns the numbers, or an error message.
 */
export function parseNumberList(text: string, integer: boolean): number[] | string {
  const normalized = text.trim().replace(/\s*(\.\.|:)\s*/g, "$1");
  if (!normalized) return "enter at least one value";
  const values: number[] = [];
  for (const item of normalized.split(/[,;\s]+/).filter(Boolean)) {
    const range = /^(-?[\d.eE+-]+)\.\.(-?[\d.eE+-]+)(?::(-?[\d.eE+-]+))?$/.exec(item);
    if (range) {
      const start = Number(range[1]);
      const stop = Number(range[2]);
      const step = range[3] === undefined ? 1 : Number(range[3]);
      if ([start, stop, step].some((n) => Number.isNaN(n))) return `invalid range "${item}"`;
      if (integer && ![start, stop, step].every(Number.isInteger)) return `"${item}" needs whole numbers`;
      if (step <= 0) return `range "${item}" needs a positive step`;
      if (stop < start) return `range "${item}" ends before it starts`;
      const count = Math.floor((stop - start) / step + 1e-9) + 1;
      if (values.length + count > 10000) return "too many values (limit 10000)";
      for (let index = 0; index < count; index += 1) {
        values.push(integer ? start + index * step : Math.round((start + index * step) * 1e10) / 1e10);
      }
    } else {
      const value = Number(item);
      if (Number.isNaN(value)) return `"${item}" is not a number`;
      if (integer && !Number.isInteger(value)) return `"${item}" is not a whole number`;
      values.push(value);
    }
  }
  return values;
}

/** Human-friendly version of a parameter value for labels and tables. */
export function formatValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : String(Number(value.toPrecision(6)));
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (Array.isArray(value)) return `${value.length} items`;
  if (typeof value === "object") {
    const record = value as { name?: string };
    return record.name ?? "object";
  }
  return String(value);
}

export function choiceLabel(field: Field | undefined, value: unknown): string {
  if (!field) return formatValue(value);
  const choice = field.choices.find((item) => item.value === String(value));
  return choice ? choice.label : formatValue(value);
}

/** Field errors from the API can be nested ("segments.0.nodes"); pick those under a prefix. */
export function errorsUnder(errors: Record<string, string>, prefix: string): Record<string, string> {
  const result: Record<string, string> = {};
  for (const [key, message] of Object.entries(errors)) {
    if (key.startsWith(`${prefix}.`)) result[key.slice(prefix.length + 1)] = message;
  }
  return result;
}

function isBlank(value: unknown): boolean {
  return value === null || value === undefined || value === "";
}

/** True when value equals the field's default. Blank, null and undefined count as the same; "3" equals 3. */
export function isDefaultValue(field: Field, value: unknown): boolean {
  const fallback = field.default;
  if (isBlank(value) || isBlank(fallback)) return isBlank(value) && isBlank(fallback);
  if (isNumericKind(field)) return Number(value) === Number(fallback);
  return JSON.stringify(value) === JSON.stringify(fallback);
}

/** Visible fields whose value differs from the default. */
export function changedFields(fields: Field[], values: Values): Field[] {
  return visibleFields(fields, values).filter((field) => !isDefaultValue(field, values[field.name]));
}

/** A value as a person would say it: choice labels, On/Off, the placeholder for blanks ("automatic"). */
export function displayValue(field: Field, value: unknown): string {
  if (isBlank(value)) return field.placeholder || "none";
  if (field.kind === "bool") return value ? "On" : "Off";
  if (field.kind === "choice" || field.choices.length) return choiceLabel(field, value);
  const number = typeof value === "string" && isNumericKind(field) ? Number(value) : value;
  const text = typeof number === "number" && Number.isInteger(number) ? number.toLocaleString("en-US") : formatValue(number);
  return field.unit ? `${text} ${field.unit}` : text;
}
