import { Group, NumberInput, SegmentedControl, Select, Stack, Text } from "@mantine/core";
import type { SolverSpec } from "../api/types";
import type { Values } from "../lib/params";
import { ParamForm } from "./fields/ParamForm";

export interface SolverSettings {
  solver: string;
  options: Record<string, Values>;
  timeout: number | string;
  logLevel: string;
}

const LOG_LABELS: Record<string, string> = {
  normal: "Normal: start, finish and statistics",
  periodic: "Progress: periodic search statistics",
  debug: "Debug: every decision (capped)",
};

export function SolverPanel({
  solvers,
  settings,
  onChange,
  errors,
}: {
  solvers: SolverSpec[];
  settings: SolverSettings;
  onChange: (settings: SolverSettings) => void;
  errors: Record<string, string>;
}) {
  const spec = solvers.find((solver) => solver.key === settings.solver) ?? solvers[0];
  const options = settings.options[spec.key] ?? {};
  const optionErrors = Object.fromEntries(
    Object.entries(errors)
      .filter(([key]) => key.startsWith("options."))
      .map(([key, message]) => [key.slice(8), message]),
  );

  return (
    <Stack gap="sm">
      <SegmentedControl
        fullWidth
        value={spec.key}
        onChange={(solver) => onChange({ ...settings, solver })}
        data={solvers.map((solver) => ({ value: solver.key, label: solver.title }))}
        aria-label="Solver"
      />
      <Text size="sm" c="dimmed">
        {spec.summary}
      </Text>
      {spec.fields.length ? (
        <ParamForm
          fields={spec.fields}
          values={options}
          errors={optionErrors}
          onChange={(name, value) => onChange({ ...settings, options: { ...settings.options, [spec.key]: { ...options, [name]: value } } })}
        />
      ) : null}
      <Group grow align="flex-start">
        <NumberInput
          label="Time limit (s)"
          description="Blank means no limit"
          value={settings.timeout}
          onChange={(timeout) => onChange({ ...settings, timeout })}
          min={0}
          step={5}
          error={errors.timeout}
        />
        <Select
          label="Log detail"
          description="What the solver writes to the log"
          value={settings.logLevel}
          onChange={(logLevel) => logLevel && onChange({ ...settings, logLevel })}
          data={Object.entries(LOG_LABELS).map(([value, label]) => ({ value, label: label.split(":")[0] }))}
          allowDeselect={false}
        />
      </Group>
    </Stack>
  );
}
