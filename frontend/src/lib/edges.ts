export type Edge = [number, number];

/** Parse "1-2, 2-3" / "1 2" lines into sorted unique pairs (lenient: skips bad items). */
export function parseEdges(text: string): { edges: Edge[]; errors: string[] } {
  const edges = new Map<string, Edge>();
  const errors: string[] = [];
  for (const raw of text.split(/[,;\n]+/)) {
    const item = raw.trim();
    if (!item) continue;
    const parts = item.split(/\s*-\s*|\s+/).filter(Boolean);
    const [u, v] = parts.map(Number);
    if (parts.length !== 2 || !Number.isInteger(u) || !Number.isInteger(v) || u < 1 || v < 1) {
      errors.push(`"${item}" is not an edge like 1-2`);
      continue;
    }
    if (u === v) {
      errors.push(`${u}-${v} is a self loop`);
      continue;
    }
    const edge: Edge = u < v ? [u, v] : [v, u];
    edges.set(`${edge[0]}-${edge[1]}`, edge);
  }
  return { edges: [...edges.values()].sort((a, b) => a[0] - b[0] || a[1] - b[1]), errors };
}

export function formatEdges(edges: Edge[]): string {
  return edges.map(([u, v]) => `${u}-${v}`).join(", ");
}

export function toggleEdge(edges: Edge[], u: number, v: number): Edge[] {
  const [a, b] = u < v ? [u, v] : [v, u];
  const exists = edges.some(([x, y]) => x === a && y === b);
  const next: Edge[] = exists ? edges.filter(([x, y]) => !(x === a && y === b)) : [...edges, [a, b]];
  return next.sort((p, q) => p[0] - q[0] || p[1] - q[1]);
}

export function edgesAsText(value: unknown): string {
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return formatEdges(value as Edge[]);
  return "";
}
