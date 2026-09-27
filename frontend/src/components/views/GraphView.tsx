import { ActionIcon, Badge, Group, Stack, Text, Tooltip, useComputedColorScheme } from "@mantine/core";
import { IconArrowsMaximize, IconRefresh } from "@tabler/icons-react";
import cytoscape, { type Core, type ElementDefinition } from "cytoscape";
import { useEffect, useMemo, useRef, useState } from "react";
import { CATEGORICAL, CHROME } from "../../lib/palette";

export interface GraphViewProps {
  nodes: number;
  edges: [number, number][];
  /** Colour index per node (1-based colours, 0 = none), e.g. a graph colouring. */
  coloring?: number[] | null;
  /** Nodes to highlight (clique / independent set). */
  selected?: number[] | null;
  /** Node order of a path (Hamiltonian path). */
  path?: number[] | null;
  /** Manual editing: click two nodes to add or remove the edge between them. */
  editable?: boolean;
  onToggleEdge?: (u: number, v: number) => void;
  height?: number;
}

const MAX_NODES_DRAWN = 600;

export function GraphView({ nodes, edges, coloring, selected, path, editable, onToggleEdge, height = 360 }: GraphViewProps) {
  const container = useRef<HTMLDivElement | null>(null);
  const cy = useRef<Core | null>(null);
  const pending = useRef<string | null>(null);
  const toggleRef = useRef(onToggleEdge);
  const [pendingNode, setPendingNode] = useState<string | null>(null);
  const scheme = useComputedColorScheme("light");
  const chrome = CHROME[scheme];
  toggleRef.current = onToggleEdge;

  const pathEdges = useMemo(() => {
    const set = new Set<string>();
    (path ?? []).forEach((node, index, list) => {
      if (index > 0) {
        const [a, b] = [list[index - 1], node].sort((x, y) => x - y);
        set.add(`${a}-${b}`);
      }
    });
    return set;
  }, [path]);

  const elements = useMemo<ElementDefinition[]>(() => {
    if (nodes > MAX_NODES_DRAWN) return [];
    const chosen = new Set(selected ?? []);
    const positions = new Map((path ?? []).map((node, index) => [node, index + 1]));
    const nodeElements: ElementDefinition[] = Array.from({ length: nodes }, (_, index) => {
      const id = index + 1;
      const color = coloring?.[index] ?? 0;
      return {
        data: {
          id: String(id),
          label: positions.has(id) ? `${id}` : String(id),
          fill: color ? CATEGORICAL[scheme][(color - 1) % 8] : chosen.has(id) ? "#f8ba1d" : undefined,
          role: chosen.has(id) ? "selected" : positions.get(id) === 1 ? "start" : positions.get(id) === nodes ? "end" : "",
          colorIndex: color,
        },
      };
    });
    const edgeElements: ElementDefinition[] = edges
      .filter(([u, v]) => u <= nodes && v <= nodes)
      .map(([u, v]) => ({
        data: {
          id: `e${u}-${v}`,
          source: String(u),
          target: String(v),
          onPath: pathEdges.has(`${u}-${v}`) || (chosen.has(u) && chosen.has(v)) ? "yes" : "no",
        },
      }));
    return [...nodeElements, ...edgeElements];
  }, [nodes, edges, coloring, selected, path, pathEdges, scheme]);

  const style = useMemo(
    () => [
      {
        selector: "node",
        style: {
          "background-color": chrome.surface,
          "border-width": 2,
          "border-color": scheme === "light" ? "#5a39bd" : "#a38ce5",
          label: "data(label)",
          color: chrome.text,
          "font-size": nodes > 60 ? 7 : 11,
          "text-valign": "center",
          "text-halign": "center",
          width: nodes > 60 ? 14 : 28,
          height: nodes > 60 ? 14 : 28,
        },
      },
      { selector: "node[fill]", style: { "background-color": "data(fill)", color: "#ffffff", "border-color": chrome.surface } },
      { selector: 'node[role = "selected"]', style: { color: "#1d1b2e", "border-color": "#a97800", "border-width": 3 } },
      { selector: 'node[role = "start"]', style: { "border-color": "#f8b50c", "border-width": 4 } },
      { selector: 'node[role = "end"]', style: { "border-color": "#f8b50c", "border-width": 4, "border-style": "double" } },
      { selector: "node.pending", style: { "border-color": "#f8b50c", "border-width": 5 } },
      {
        selector: "edge",
        style: { width: nodes > 100 ? 0.6 : 1.4, "line-color": scheme === "light" ? "#c3c2b7" : "#55534f", "curve-style": "straight" },
      },
      { selector: 'edge[onPath = "yes"]', style: { width: 4, "line-color": "#f8ba1d", "z-index": 10 } },
    ],
    [chrome, scheme, nodes],
  );

  // Create the instance once.
  useEffect(() => {
    if (!container.current) return;
    const instance = cytoscape({
      container: container.current,
      elements: [],
      wheelSensitivity: 0.3,
      minZoom: 0.2,
      maxZoom: 4,
      boxSelectionEnabled: false,
    });
    instance.on("tap", "node", (event) => {
      const id = event.target.id() as string;
      if (!toggleRef.current) return;
      const first = pending.current;
      if (first && first !== id) {
        toggleRef.current(Number(first), Number(id));
        instance.$id(first).removeClass("pending");
        pending.current = null;
        setPendingNode(null);
      } else if (first === id) {
        instance.$id(first).removeClass("pending");
        pending.current = null;
        setPendingNode(null);
      } else {
        event.target.addClass("pending");
        pending.current = id;
        setPendingNode(id);
      }
    });
    instance.on("tap", (event) => {
      if (event.target === instance && pending.current) {
        instance.$id(pending.current).removeClass("pending");
        pending.current = null;
        setPendingNode(null);
      }
    });
    cy.current = instance;
    return () => {
      instance.destroy();
      cy.current = null;
    };
  }, []);

  // Update elements; keep positions of nodes that survive, lay out otherwise.
  const layoutSignature = `${nodes}|${editable ? "edit" : edges.map((e) => e.join("-")).join(",")}`;
  const lastLayout = useRef<string>("");
  useEffect(() => {
    const instance = cy.current;
    if (!instance) return;
    const positions = new Map<string, { x: number; y: number }>();
    instance.nodes().forEach((node) => {
      positions.set(node.id(), { ...node.position() });
    });
    instance.batch(() => {
      instance.elements().remove();
      instance.add(elements);
      instance.style(style as never);
    });
    const needsLayout = lastLayout.current !== layoutSignature || positions.size === 0;
    if (needsLayout && (!editable || instance.nodes().filter((node) => !positions.has(node.id())).length > 0 || lastLayout.current === "")) {
      runLayout(instance, nodes);
    } else {
      instance.nodes().forEach((node) => {
        const position = positions.get(node.id());
        if (position) node.position(position);
      });
    }
    if (pending.current) instance.$id(pending.current).addClass("pending");
    lastLayout.current = layoutSignature;
  }, [elements, style, layoutSignature, editable, nodes]);

  if (nodes > MAX_NODES_DRAWN) {
    return (
      <Text size="sm" c="dimmed">
        {nodes} nodes and {edges.length} edges: too large to draw.
      </Text>
    );
  }

  const colorsUsed = coloring ? [...new Set(coloring.filter(Boolean))].sort((a, b) => a - b) : [];

  return (
    <Stack gap={6}>
      <div className="wz-graph" style={{ height }}>
        <div ref={container} style={{ position: "absolute", inset: 0 }} aria-label={`Graph with ${nodes} nodes and ${edges.length} edges`} role="img" />
        <Group gap={4} style={{ position: "absolute", right: 8, top: 8 }}>
          <Tooltip label="Re-arrange">
            <ActionIcon variant="default" size="sm" aria-label="Re-arrange graph" onClick={() => cy.current && runLayout(cy.current, nodes, true)}>
              <IconRefresh size={14} />
            </ActionIcon>
          </Tooltip>
          <Tooltip label="Fit to view">
            <ActionIcon variant="default" size="sm" aria-label="Fit graph" onClick={() => cy.current?.fit(undefined, 20)}>
              <IconArrowsMaximize size={14} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </div>
      <Group gap="xs" justify="space-between">
        <Text size="xs" c="dimmed">
          {nodes} nodes, {edges.length} edges
          {editable ? (pendingNode ? ` - now click another node to add/remove an edge from ${pendingNode}` : " - click two nodes to add or remove an edge; drag to move") : ""}
        </Text>
        {colorsUsed.length ? (
          <Group gap={6}>
            {colorsUsed.map((color) => (
              <Badge
                key={color}
                size="sm"
                variant="outline"
                color="gray"
                leftSection={<span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 5, background: CATEGORICAL[scheme][(color - 1) % 8] }} />}
              >
                color {color}
              </Badge>
            ))}
          </Group>
        ) : null}
        {selected?.length ? (
          <Badge size="sm" variant="light" color="gold">
            chosen: {selected.join(", ")}
          </Badge>
        ) : null}
        {path?.length ? (
          <Text size="xs" c="dimmed">
            path: {path.join(" -> ")}
          </Text>
        ) : null}
      </Group>
      {colorsUsed.some((color) => color > 8) ? (
        <Text size="xs" c="dimmed">
          More than 8 colours: colours repeat after the eighth; the solver's answer was checked edge by edge.
        </Text>
      ) : null}
    </Stack>
  );
}

function runLayout(instance: Core, nodes: number, randomize = false) {
  const options =
    nodes <= 150
      ? { name: "cose", animate: false, randomize, padding: 24, nodeRepulsion: () => 9000, idealEdgeLength: () => 60, fit: true }
      : { name: "circle", animate: false, padding: 16, fit: true };
  instance.layout(options as never).run();
}
