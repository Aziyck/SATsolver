import { Paper, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import type { BenchmarkRequest, Catalog, Rule, SolverEntry } from "../api/types";
import { formatSeconds } from "../lib/format";
import { FactsList } from "./Display";
import { SolverSettingsTable } from "./SolverSettingsTable";

export function ruleText(rule: Rule, catalog: Catalog): string {
  const solver = catalog.solvers.find((item) => item.key === rule.solver)?.title ?? rule.solver;
  const action = rule.action === "skip" ? "skip" : `cap the time at ${formatSeconds(rule.seconds ?? 0)}`;
  return `${solver}: ${action} from ${rule.min_variables} variables`;
}

/** The solver entry that produced a row: rows are numbered case * solvers + position. */
export function entryForRow(request: BenchmarkRequest, rowIndex: number): SolverEntry | undefined {
  const solvers = request.solvers ?? [];
  return solvers.length ? solvers[rowIndex % solvers.length] : undefined;
}

/** Everything a benchmark ran with: run-wide settings, limit rules, and each solver's options. */
export function BenchmarkSetup({ request, catalog }: { request: BenchmarkRequest; catalog: Catalog }) {
  const problems = (request.problems ?? []).map((key) => catalog.problems.find((item) => item.key === key)?.title ?? key);
  const rules = request.rules ?? [];

  return (
    <Stack gap="lg">
      <FactsList
        facts={[
          { label: problems.length > 1 ? "Problems" : "Problem", value: problems.join(", ") },
          { label: "Segments", value: (request.segments ?? []).length },
          { label: "Repeats", value: request.repeats ?? 1 },
          { label: "Time limit per run", value: request.timeout === null || request.timeout === undefined ? "none" : formatSeconds(request.timeout) },
          { label: "Parallel workers", value: request.workers ?? 1 },
          { label: "Benchmark seed", value: request.seed === null || request.seed === undefined || request.seed === "" ? "none" : String(request.seed) },
          { label: "Log level", value: request.log_level ?? "normal" },
        ]}
      />
      <div>
        <Text fw={600} size="sm" mb={4}>
          Limit rules
        </Text>
        {rules.length ? (
          rules.map((rule, index) => (
            <Text key={index} size="sm">
              {ruleText(rule, catalog)}
            </Text>
          ))
        ) : (
          <Text size="sm" c="dimmed">
            None: every solver ran every case with the time limit above.
          </Text>
        )}
      </div>
      <div>
        <Title order={4} mb="xs">
          Solvers
        </Title>
        <SimpleGrid cols={{ base: 1, lg: 2 }} spacing="md">
          {(request.solvers ?? []).map((entry, index) => {
            const spec = catalog.solvers.find((item) => item.key === entry.solver);
            return (
              <Paper key={index} withBorder p="md" radius="md">
                <Text fw={650} mb="xs">
                  {entry.label || spec?.title || entry.solver}
                </Text>
                {spec ? (
                  <SolverSettingsTable spec={spec} options={entry.options} />
                ) : (
                  <Text size="sm" c="dimmed">
                    This solver is no longer available.
                  </Text>
                )}
              </Paper>
            );
          })}
        </SimpleGrid>
      </div>
    </Stack>
  );
}
