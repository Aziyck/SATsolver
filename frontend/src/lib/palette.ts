// Chart colours: the validated reference palette (categorical order is part of
// its colour-blind safety, so series take slots in a fixed order, never cycled).

export type Scheme = "light" | "dark";

export const CATEGORICAL: Record<Scheme, string[]> = {
  light: ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"],
  dark: ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#008300", "#9085e9", "#e66767"],
};

export const CHROME: Record<Scheme, { surface: string; text: string; secondary: string; muted: string; grid: string; axis: string }> = {
  light: { surface: "#fcfcfb", text: "#0b0b0b", secondary: "#52514e", muted: "#898781", grid: "#e1e0d9", axis: "#c3c2b7" },
  dark: { surface: "#1a1a19", text: "#ffffff", secondary: "#c3c2b7", muted: "#898781", grid: "#2c2c2a", axis: "#383835" },
};

export const STATUS_COLORS = { good: "#0ca30c", warning: "#fab219", serious: "#ec835a", critical: "#d03b3b" };

/** Solver-run statuses in stacking order, each with a fixed colour (identity follows the status, not its rank). */
export const RUN_STATUS_ORDER = ["SAT", "UNSAT", "UNKNOWN", "TIMEOUT", "SKIPPED", "CANCELLED", "ERROR"] as const;

export function runStatusColor(status: string, scheme: Scheme): string {
  const slots = CATEGORICAL[scheme];
  switch (status) {
    case "SAT":
      return slots[0];
    case "UNSAT":
      return slots[1];
    case "UNKNOWN":
      return slots[2];
    case "TIMEOUT":
      return slots[3];
    case "ERROR":
      return STATUS_COLORS.critical;
    default:
      return scheme === "light" ? "#b9b8b2" : "#5c5b57";
  }
}

/** Colour for the n-th series (0-based); null past the eighth slot. */
export function seriesColor(index: number, scheme: Scheme): string | null {
  return CATEGORICAL[scheme][index] ?? null;
}
