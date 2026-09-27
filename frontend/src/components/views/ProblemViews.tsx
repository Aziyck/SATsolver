import { Alert, Stack, Text } from "@mantine/core";
import type { ResultView } from "../../api/types";
import { AssignmentView, ClauseSample } from "./AssignmentView";
import { GraphView } from "./GraphView";
import { QueensBoard } from "./QueensBoard";
import { SudokuBoard } from "./SudokuBoard";

/** The answer drawn on top of the problem input. decoded = null shows just the input. */
export function AnswerView({
  view,
  visual,
  decoded,
}: {
  view: ResultView;
  visual: any;
  decoded: any;
}) {
  if (!visual) return null;
  switch (view) {
    case "sudoku":
      return <SudokuBoard givens={visual.givens} solution={decoded?.grid ?? null} />;
    case "queens":
      return <QueensBoard size={visual.size} queens={decoded?.queens ?? null} />;
    case "graph":
      if (visual.too_large) {
        return (
          <Text size="sm" c="dimmed">
            The graph has {visual.edge_count} edges, too many to draw.
          </Text>
        );
      }
      return (
        <GraphView
          nodes={visual.nodes}
          edges={visual.edges}
          coloring={decoded?.coloring ?? null}
          selected={decoded?.selected ?? null}
          path={decoded?.path ?? null}
        />
      );
    case "assignment":
      if (decoded) {
        return <AssignmentView bits={decoded.bits} variables={decoded.variables} trueCount={decoded.true_count} />;
      }
      return (
        <Stack gap="xs">
          {visual.sample ? <ClauseSample sample={visual.sample} clauses={visual.clauses} /> : null}
          {visual.warnings?.length ? (
            <Alert color="yellow" variant="light" title="Parser warnings">
              {visual.warnings.map((warning: string) => (
                <Text key={warning} size="sm">
                  {warning}
                </Text>
              ))}
            </Alert>
          ) : null}
        </Stack>
      );
  }
}
