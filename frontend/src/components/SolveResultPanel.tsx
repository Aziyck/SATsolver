import { Alert, Button, Card, Group, Loader, Progress, SimpleGrid, Stack, Table, Tabs, Text, ThemeIcon, Title, Tooltip } from "@mantine/core";
import {
  IconAlertTriangle,
  IconCircleCheck,
  IconDownload,
  IconEdit,
  IconFileCode,
  IconListDetails,
  IconPlayerStop,
  IconRefresh,
  IconSparkles,
  IconTable,
  IconTrash,
} from "@tabler/icons-react";
import { useEffect, useState } from "react";
import { urls } from "../api/client";
import { useJob, useJobActions, useProblem } from "../api/queries";
import type { JobDetail } from "../api/types";
import { duration, formatSeconds, formatStat, statLabel } from "../lib/format";
import { isActive, JobStatusBadge, RUN_STATUS, RunStatusBadge } from "../lib/status";
import { CnfViewer, FactsList, LogViewer } from "./Display";
import { AnswerView } from "./views/ProblemViews";

function useTicker(active: boolean) {
  const [, setTick] = useState(0);
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => setTick((tick) => tick + 1), 500);
    return () => clearInterval(timer);
  }, [active]);
}

export function SolveResultPanel({
  jobId,
  onEdit,
  onOpenAs,
  onDeleted,
}: {
  jobId: number;
  onEdit: (job: JobDetail) => void;
  onOpenAs: (problem: string, params: Record<string, unknown>) => void;
  onDeleted: () => void;
}) {
  const { data: job, isLoading, isError } = useJob(jobId);
  const problem = useProblem(job?.problems[0]);
  const actions = useJobActions();
  const active = job ? isActive(job.status) : false;
  useTicker(active);
  const [tab, setTab] = useState<string | null>("answer");

  if (isLoading) return <Loader />;
  if (isError || !job) {
    return (
      <Alert color="gray" title="Job not found">
        This job was deleted.
      </Alert>
    );
  }

  const result = job.result;
  const instance = job.instance;
  const elapsed = duration(job.started_at, job.finished_at);
  const status = result?.status;
  const appHeader = instance?.visual?.app_header as { problem?: string; params?: Record<string, unknown> } | undefined;

  return (
    <Card>
      <Stack gap="md">
        <Group justify="space-between" align="flex-start" wrap="nowrap">
          <Stack gap={4} style={{ minWidth: 0 }}>
            <Group gap="xs">
              <Text c="dimmed" size="sm" fw={600}>
                {job.label}
              </Text>
              <JobStatusBadge status={job.status} />
            </Group>
            <Title order={4} lineClamp={2}>
              {instance?.name ?? job.title}
            </Title>
          </Stack>
          <Group gap={6} wrap="nowrap">
            {active ? (
              <Button color="red" variant="light" size="xs" leftSection={<IconPlayerStop size={14} />} onClick={() => actions.cancel.mutate(job.id)}>
                Stop
              </Button>
            ) : (
              <>
                <Tooltip label="Load these parameters into the form">
                  <Button variant="default" size="xs" leftSection={<IconEdit size={14} />} onClick={() => onEdit(job)}>
                    Edit
                  </Button>
                </Tooltip>
                <Tooltip label="Run exactly the same job again">
                  <Button variant="default" size="xs" leftSection={<IconRefresh size={14} />} onClick={() => actions.rerun.mutate(job.id)}>
                    Rerun
                  </Button>
                </Tooltip>
                <Tooltip label="Delete this job">
                  <Button
                    variant="subtle"
                    color="red"
                    size="xs"
                    aria-label="Delete job"
                    onClick={() => actions.remove.mutate(job.id, { onSuccess: onDeleted })}
                  >
                    <IconTrash size={14} />
                  </Button>
                </Tooltip>
              </>
            )}
          </Group>
        </Group>

        {active ? (
          <Stack gap={4}>
            <Progress value={100} animated striped size="sm" />
            <Text size="sm" c="dimmed">
              {job.progress.message || (job.status === "queued" ? "Waiting for a free worker..." : "Working...")} · {formatSeconds(elapsed)}
            </Text>
          </Stack>
        ) : null}

        {job.status === "failed" ? (
          <Alert color="red" icon={<IconAlertTriangle />} title="The job failed">
            <Text size="sm">{job.error}</Text>
            {job.errors
              ? Object.entries(job.errors).map(([field, message]) => (
                  <Text key={field} size="sm">
                    {field}: {message}
                  </Text>
                ))
              : null}
          </Alert>
        ) : null}

        {result ? (
          <SimpleGrid cols={{ base: 2, sm: 4 }} spacing="sm">
            <div>
              <Text size="xs" c="dimmed">
                Answer
              </Text>
              <Group gap={6} mt={2}>
                <RunStatusBadge status={status} size="lg" />
              </Group>
            </div>
            <div>
              <Text size="xs" c="dimmed">
                Solver time
              </Text>
              <Text fw={650} size="lg">
                {formatSeconds(result.elapsed)}
              </Text>
            </div>
            <div>
              <Text size="xs" c="dimmed">
                Solver
              </Text>
              <Text fw={650} size="lg">
                {result.solver_label}
              </Text>
            </div>
            <div>
              <Text size="xs" c="dimmed">
                Check
              </Text>
              {result.verified ? (
                <Tooltip label="The model satisfies every clause, and the decoded answer passed the problem's own checks.">
                  <Group gap={4} mt={2}>
                    <ThemeIcon color="green" variant="light" size="sm" radius="xl">
                      <IconCircleCheck size={14} />
                    </ThemeIcon>
                    <Text fw={650} c="green">
                      Verified
                    </Text>
                  </Group>
                </Tooltip>
              ) : result.verified === false ? (
                <Text fw={650} c="red">
                  Failed
                </Text>
              ) : (
                <Text fw={650} c="dimmed">
                  {status === "UNSAT" ? "Proof" : "-"}
                </Text>
              )}
            </div>
          </SimpleGrid>
        ) : null}

        {result && status ? (
          <Text size="sm" c="dimmed">
            {RUN_STATUS[status].description}
            {result.error ? ` ${result.error}` : ""}
          </Text>
        ) : null}

        {result?.expected && (status === "SAT" || status === "UNSAT") && result.expected !== status ? (
          <Alert color="red" icon={<IconAlertTriangle />} title="Unexpected answer">
            This generator guarantees {result.expected}, but the solver answered {status}. That points to a solver bug.
          </Alert>
        ) : null}
        {result?.check_errors?.length ? (
          <Alert color="red" icon={<IconAlertTriangle />} title="The answer did not pass the checks">
            {result.check_errors.slice(0, 5).map((error) => (
              <Text key={error} size="sm">
                {error}
              </Text>
            ))}
          </Alert>
        ) : null}

        {appHeader?.problem && appHeader.params ? (
          <Alert color="wizard" icon={<IconSparkles />} title="This CNF was exported by WizSAT">
            <Group justify="space-between">
              <Text size="sm">It was generated from a {appHeader.problem.replace(/_/g, " ")} instance. Reopen it with its original parameters to see a decoded answer.</Text>
              <Button size="xs" onClick={() => onOpenAs(appHeader.problem as string, appHeader.params as Record<string, unknown>)}>
                Open as that problem
              </Button>
            </Group>
          </Alert>
        ) : null}

        <Tabs value={tab} onChange={setTab} keepMounted={false}>
          <Tabs.List>
            <Tabs.Tab value="answer" leftSection={<IconSparkles size={14} />}>
              {result?.decoded ? "Answer" : "Input"}
            </Tabs.Tab>
            <Tabs.Tab value="instance" leftSection={<IconFileCode size={14} />} disabled={!instance}>
              CNF
            </Tabs.Tab>
            <Tabs.Tab value="stats" leftSection={<IconTable size={14} />} disabled={!result}>
              Statistics
            </Tabs.Tab>
            <Tabs.Tab value="log" leftSection={<IconListDetails size={14} />}>
              Log
            </Tabs.Tab>
          </Tabs.List>

          <Tabs.Panel value="answer" pt="md">
            {instance && problem ? (
              <Stack gap="md">
                <AnswerView view={problem.result_view} visual={instance.visual} decoded={result?.decoded ?? null} />
                <FactsList
                  facts={[
                    ...instance.facts,
                    { label: "CNF variables", value: instance.variables },
                    { label: "CNF clauses", value: instance.clauses },
                    { label: "Encoding time", value: formatSeconds(instance.encode_seconds) },
                  ]}
                />
                {result?.model_file ? (
                  <Button component="a" href={urls.file(job.id, result.model_file)} variant="subtle" size="xs" leftSection={<IconDownload size={14} />} style={{ alignSelf: "flex-start" }}>
                    Download the model (DIMACS "v" lines)
                  </Button>
                ) : null}
              </Stack>
            ) : (
              <Text size="sm" c="dimmed">
                The instance appears here once it is encoded.
              </Text>
            )}
          </Tabs.Panel>
          <Tabs.Panel value="instance" pt="md">
            {instance?.cnf_file ? <CnfViewer jobId={job.id} /> : null}
          </Tabs.Panel>
          <Tabs.Panel value="stats" pt="md">
            {result ? (
              <Stack gap="xs">
                <Text size="sm" c="dimmed">
                  Options: {result.options_summary}
                  {result.timeout !== null ? ` · time limit ${formatSeconds(result.timeout)}` : " · no time limit"}
                </Text>
                <Table striped withTableBorder className="wz-num">
                  <Table.Tbody>
                    {Object.entries(result.stats).map(([key, value]) => (
                      <Table.Tr key={key}>
                        <Table.Td>{statLabel(key)}</Table.Td>
                        <Table.Td ta="right">{formatStat(value)}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Stack>
            ) : null}
          </Tabs.Panel>
          <Tabs.Panel value="log" pt="md">
            <LogViewer jobId={job.id} initial={job.logs} />
          </Tabs.Panel>
        </Tabs>
      </Stack>
    </Card>
  );
}
