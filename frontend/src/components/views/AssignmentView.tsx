import { Group, Stack, Text } from "@mantine/core";
import { formatCount } from "../../lib/format";

const MAX_CELLS = 2000;

/** A truth assignment as a grid of cells: filled = true. Hover a cell to see its variable. */
export function AssignmentView({ bits, variables, trueCount }: { bits?: string; variables: number; trueCount: number }) {
  if (!bits) {
    return (
      <Text size="sm" c="dimmed">
        {formatCount(trueCount)} of {formatCount(variables)} variables are true. The assignment is too large to display; download the model instead.
      </Text>
    );
  }
  const shown = bits.slice(0, MAX_CELLS);
  const columns = variables <= 100 ? 10 : variables <= 400 ? 20 : 40;
  return (
    <Stack gap="xs">
      <Group gap="md">
        <Text size="sm">
          <b>{formatCount(trueCount)}</b> true, <b>{formatCount(variables - trueCount)}</b> false
        </Text>
        <Group gap={6}>
          <span className="wz-bit" data-value="1" style={{ width: 12, height: 12, display: "inline-block" }} />
          <Text size="xs" c="dimmed">
            true
          </Text>
          <span className="wz-bit" data-value="0" style={{ width: 12, height: 12, display: "inline-block" }} />
          <Text size="xs" c="dimmed">
            false
          </Text>
        </Group>
      </Group>
      <div className="wz-bits" style={{ gridTemplateColumns: `repeat(${columns}, minmax(0, 22px))` }}>
        {[...shown].map((bit, index) => (
          <div key={index} className="wz-bit" data-value={bit} title={`x${index + 1} = ${bit === "1" ? "true" : "false"}`}>
            {variables <= 100 ? index + 1 : ""}
          </div>
        ))}
      </div>
      {bits.length > MAX_CELLS ? (
        <Text size="xs" c="dimmed">
          Showing the first {MAX_CELLS} of {formatCount(variables)} variables.
        </Text>
      ) : null}
    </Stack>
  );
}

export function ClauseSample({ sample, clauses }: { sample: number[][]; clauses: number }) {
  return (
    <Stack gap={4}>
      <Text size="xs" c="dimmed">
        First clauses ({formatCount(clauses)} in total):
      </Text>
      {sample.map((clause, index) => (
        <Text key={index} size="sm" className="wz-mono">
          ({clause.map((lit) => (lit > 0 ? `x${lit}` : `¬x${-lit}`)).join(" ∨ ")})
        </Text>
      ))}
    </Stack>
  );
}
