import { Group, NumberInput, SegmentedControl, Select, Stack, Text } from "@mantine/core";
import { defaultValues, type Values } from "../lib/params";
import type { SolverSpec } from "../api/types";
import { FieldLabel, ParamForm, ResetToDefaults, useHelpLine } from "./fields/ParamForm";

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
  const helpLine = useHelpLine();
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
      <Group grow align="flex-start">
        <NumberInput
          label={<FieldLabel text="Time limit (s)" help="The run stops with TIMEOUT after this long. Blank means no limit." />}
          description={helpLine("Blank means no limit")}
          value={settings.timeout}
          onChange={(timeout) => onChange({ ...settings, timeout })}
          min={0}
          step={5}
          error={errors.timeout}
        />
        <Select
          label={<FieldLabel text="Log detail" help="What the solver writes to the log. Progress and Debug slow the solver down." />}
          description={helpLine("What the solver writes to the log")}
          value={settings.logLevel}
          onChange={(logLevel) => logLevel && onChange({ ...settings, logLevel })}
          data={Object.entries(LOG_LABELS).map(([value, label]) => ({ value, label: label.split(":")[0] }))}
          allowDeselect={false}
        />
      </Group>
      <Group justify="space-between" align="flex-start" wrap="nowrap" gap="xs">
        <Text size="sm" c="dimmed">
          {spec.summary}
        </Text>
        <ResetToDefaults
          fields={spec.fields}
          values={{ ...defaultValues(spec.fields), ...options }}
          onReset={() => onChange({ ...settings, options: { ...settings.options, [spec.key]: defaultValues(spec.fields) } })}
        />
      </Group>
      {spec.fields.length ? (
        <ParamForm
          fields={spec.fields}
          values={{ ...defaultValues(spec.fields), ...options }}
          errors={optionErrors}
          resettable
          onChange={(name, value) => onChange({ ...settings, options: { ...settings.options, [spec.key]: { ...options, [name]: value } } })}
        />
      ) : null}
    </Stack>
  );
}
