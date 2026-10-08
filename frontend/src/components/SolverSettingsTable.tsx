import { Stack, Table, Text, Tooltip } from "@mantine/core";
import type { Field, SolverSpec, Stats } from "../api/types";
import { formatSeconds, formatStat, statHelp, statLabel } from "../lib/format";
import { defaultValues, displayValue, isDefaultValue, isVisible, type Values } from "../lib/params";

/** A setting that is not a solver option (time limit, log level), shown in the same table. */
export interface ExtraSetting {
  label: string;
  help: string;
  value: string;
  default?: string;
}

/**
 * The options a solver ran with, one row per option: what it means, the value
 * used and the default, with changed values marked. Options hidden by another
 * option (a fixed restart interval while Luby restarts are on) are left out
 * because the solver ignored them.
 */
export function SolverSettingsTable({ spec, options, extra = [] }: { spec: SolverSpec; options: Record<string, unknown> | undefined; extra?: ExtraSetting[] }) {
  const values: Values = { ...defaultValues(spec.fields), ...(options ?? {}) };
  const fields = spec.fields.filter((field) => isVisible(field, values));
  const known = new Set(spec.fields.map((field) => field.name));
  const unknown = Object.entries(options ?? {}).filter(([name]) => !known.has(name));
  const changed = fields.filter((field) => !isDefaultValue(field, values[field.name])).length;

  return (
    <Stack gap="xs">
      <Text size="sm" c="dimmed">
        {spec.title}: {spec.summary}{" "}
        {fields.length ? (changed ? `${changed} of ${fields.length} options changed from the default.` : "Every option at its default.") : null}
      </Text>
      <Table withTableBorder verticalSpacing={6} fz="sm" className="wz-settings">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Setting</Table.Th>
            <Table.Th>Value used</Table.Th>
            <Table.Th visibleFrom="xs">Default</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {fields.map((field) => (
            <SettingRow key={field.name} field={field} value={values[field.name]} />
          ))}
          {extra.map((setting) => (
            <Table.Tr key={setting.label}>
              <Table.Td>
                <Text size="sm" fw={500}>
                  {setting.label}
                </Text>
                <Text size="xs" c="dimmed">
                  {setting.help}
                </Text>
              </Table.Td>
              <Table.Td>
                <Text size="sm" fw={600} style={{ whiteSpace: "nowrap" }}>
                  {setting.value}
                </Text>
              </Table.Td>
              <Table.Td visibleFrom="xs">
                <Text size="sm" c="dimmed" style={{ whiteSpace: "nowrap" }}>
                  {setting.default ?? ""}
                </Text>
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
      {unknown.length ? (
        <Text size="xs" c="dimmed">
          Also in the request, but not an option of {spec.title} (any more): {unknown.map(([name, value]) => `${name}=${String(value)}`).join(", ")}.
        </Text>
      ) : null}
    </Stack>
  );
}

function SettingRow({ field, value }: { field: Field; value: unknown }) {
  const changed = !isDefaultValue(field, value);
  return (
    <Table.Tr className={changed ? "wz-changed" : undefined}>
      <Table.Td>
        <Text size="sm" fw={500}>
          {field.label}
        </Text>
        {field.help ? (
          <Text size="xs" c="dimmed">
            {field.help}
          </Text>
        ) : null}
      </Table.Td>
      <Table.Td>
        <Text size="sm" fw={600} className="wz-num" style={{ whiteSpace: "nowrap" }}>
          {displayValue(field, value)}
        </Text>
        {changed ? (
          <Text size="xs" c="var(--mantine-primary-color-filled)" fw={600}>
            changed
          </Text>
        ) : null}
      </Table.Td>
      <Table.Td visibleFrom="xs">
        <Text size="sm" c="dimmed" className="wz-num" style={{ whiteSpace: "nowrap" }}>
          {displayValue(field, field.default)}
        </Text>
      </Table.Td>
    </Table.Tr>
  );
}

/** Solver statistics with a readable label; hovering a label explains the number. */
export function StatsTable({ stats, size = "sm" }: { stats: Stats; size?: "xs" | "sm" }) {
  return (
    <Table striped withTableBorder className="wz-num" fz={size}>
      <Table.Tbody>
        {Object.entries(stats).map(([key, value]) => {
          const help = statHelp(key);
          return (
            <Table.Tr key={key}>
              <Table.Td>
                <Tooltip label={help} disabled={!help} multiline maw={320} position="top-start">
                  <span className={help ? "wz-explained" : undefined}>{statLabel(key)}</span>
                </Tooltip>
              </Table.Td>
              <Table.Td ta="right">{key === "elapsed" && typeof value === "number" ? formatSeconds(value) : formatStat(value)}</Table.Td>
            </Table.Tr>
          );
        })}
      </Table.Tbody>
    </Table>
  );
}
