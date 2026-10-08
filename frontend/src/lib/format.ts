export function formatSeconds(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "-";
  if (seconds === 0) return "0 s";
  if (seconds < 0.001) return `${(seconds * 1e6).toFixed(0)} µs`;
  if (seconds < 1) return `${(seconds * 1000).toFixed(seconds < 0.01 ? 2 : 1)} ms`;
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 2 : 1)} s`;
  const minutes = Math.floor(seconds / 60);
  return `${minutes} min ${Math.round(seconds - minutes * 60)} s`;
}

const compact = new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 });
const grouped = new Intl.NumberFormat("en");

export function formatCount(value: number | null | undefined, style: "grouped" | "compact" = "grouped"): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "-";
  return style === "compact" && Math.abs(value) >= 10_000 ? compact.format(value) : grouped.format(value);
}

export function formatStat(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "number") return Number.isInteger(value) ? grouped.format(value) : value.toPrecision(4);
  if (typeof value === "boolean") return value ? "on" : "off";
  return String(value);
}

export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "-";
  const date = new Date(iso);
  const today = new Date();
  const sameDay = date.toDateString() === today.toDateString();
  return sameDay
    ? date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })
    : date.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
}

export function duration(start: string | null, end: string | null): number | null {
  if (!start) return null;
  const finish = end ? new Date(end).getTime() : Date.now();
  return (finish - new Date(start).getTime()) / 1000;
}

export function statLabel(key: string): string {
  const labels: Record<string, string> = {
    decisions: "Decisions",
    conflicts: "Conflicts",
    propagations: "Propagations",
    learned_clauses: "Learned clauses",
    active_learned_clauses: "Active learned clauses",
    deleted_learned_clauses: "Deleted learned clauses",
    avg_lbd: "Average LBD",
    restarts: "Restarts",
    reductions: "Clause cleanups",
    max_depth: "Max decision depth",
    tries: "Tries",
    flips: "Flips",
    best_unsatisfied: "Best unsatisfied",
    termination_reason: "Stopped because",
    selection_mode: "Strategy",
    adaptive_noise: "Adaptive noise",
    final_noise: "Final noise",
    flip_make_total: "Make total",
    flip_break_total: "Break total",
    last_make: "Last make",
    last_break: "Last break",
    stagnation_limit: "Stagnation limit",
    elapsed: "Solver time",
    timeout: "Timeout",
  };
  return labels[key] ?? key.replace(/_/g, " ").replace(/^\w/, (char) => char.toUpperCase());
}
