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

/** Label and one-line explanation for every statistic a solver reports. */
const STATS: Record<string, [string, string]> = {
  decisions: ["Decisions", "Times the solver guessed a value for a variable."],
  conflicts: ["Conflicts", "Times a guess led to a clause with every literal false, forcing a backtrack."],
  propagations: ["Propagations", "Values forced by unit propagation (a clause with one literal left)."],
  learned_clauses: ["Learned clauses", "Clauses CDCL derived from conflicts so it never repeats the same mistake."],
  active_learned_clauses: ["Active learned clauses", "Learned clauses still kept at the end (the rest were cleaned up)."],
  deleted_learned_clauses: ["Deleted learned clauses", "Learned clauses thrown away by the clean-ups to keep propagation fast."],
  avg_lbd: ["Average LBD", "Average number of decision levels in a learned clause; lower means a more useful clause."],
  restarts: ["Restarts", "Times CDCL dropped all its guesses (keeping what it learned) to start the search again."],
  reductions: ["Clause cleanups", "Times CDCL deleted its least useful learned clauses."],
  max_depth: ["Max decision depth", "Most guesses DPLL had open at the same time."],
  tries: ["Tries", "Random starting assignments used; each try runs at most 'max flips' flips."],
  flips: ["Flips", "Variables flipped in total over all tries."],
  best_unsatisfied: ["Best unsatisfied", "Fewest clauses left false at any moment; 0 means a model was found."],
  termination_reason: ["Stopped because", "Why the search ended."],
  selection_mode: ["Strategy", "How a variable is picked from a false clause."],
  adaptive_noise: ["Adaptive noise", "Whether WalkSAT tuned its noise during the run instead of keeping it fixed."],
  final_noise: ["Final noise", "Noise at the end of the run (differs from the setting only with adaptive noise)."],
  stagnation_limit: ["Stagnation limit", "Flips without progress before adaptive noise raises the noise."],
  free_flips: ["Free flips", "Flips that broke no clause; WalkSAT always takes such a move when it has one."],
  noise_flips: ["Random flips", "Flips of a random variable of the clause (taken with probability 'noise')."],
  greedy_flips: ["Greedy flips", "Flips of the variable that breaks the fewest clauses."],
  cb: ["cb", "Base of ProbSAT's weight function: a higher value avoids flips that break clauses more strongly."],
  weight_function: ["Weight function", "ProbSAT's formula for turning a break count into a probability weight."],
  flip_break_total: ["Break total", "Sum of the break counts of every flip: clauses made false along the way."],
  last_break: ["Last break", "Break count of the last flip."],
  elapsed: ["Solver time", "Time spent inside the solver, without encoding and checking."],
  timeout: ["Timeout", "The time limit for this run."],
};

export function statLabel(key: string): string {
  return STATS[key]?.[0] ?? key.replace(/_/g, " ").replace(/^\w/, (char) => char.toUpperCase());
}

export function statHelp(key: string): string {
  return STATS[key]?.[1] ?? "";
}
