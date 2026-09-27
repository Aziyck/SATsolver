import { ActionIcon, Button, Card, Group, Progress, SegmentedControl, Stack, Table, Text, TextInput, Title, Tooltip } from "@mantine/core";
import { IconPlayerStop, IconSearch, IconTrash } from "@tabler/icons-react";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { sortedJobs, useLive } from "../api/live";
import { useJobActions } from "../api/queries";
import type { JobKind } from "../api/types";
import { jobPath, jobProgress, KindIcon } from "../components/JobsDrawer";
import { duration, formatSeconds, formatTime } from "../lib/format";
import { isActive, JobStatusBadge, RunStatusBadge } from "../lib/status";

export default function JobsPage() {
  const jobs = useLive((state) => state.jobs);
  const navigate = useNavigate();
  const actions = useJobActions();
  const [kind, setKind] = useState<"all" | JobKind>("all");
  const [query, setQuery] = useState("");
  const list = useMemo(
    () =>
      sortedJobs(jobs).filter(
        (job) => (kind === "all" || job.kind === kind) && (!query || `${job.label} ${job.title}`.toLowerCase().includes(query.toLowerCase())),
      ),
    [jobs, kind, query],
  );
  const finished = list.filter((job) => !isActive(job.status)).length;

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <div>
          <Title order={2}>Jobs</Title>
          <Text c="dimmed">Every solve, encoding and benchmark, newest first. Results are kept until you delete them.</Text>
        </div>
        <Button
          variant="default"
          color="red"
          leftSection={<IconTrash size={16} />}
          disabled={!finished}
          onClick={() => actions.clear.mutate(kind === "all" ? undefined : [kind])}
        >
          Delete finished ({finished})
        </Button>
      </Group>
      <Group gap="sm">
        <SegmentedControl
          value={kind}
          onChange={(value) => setKind(value as typeof kind)}
          data={[
            { value: "all", label: "All" },
            { value: "solve", label: "Solves" },
            { value: "generate", label: "Encodings" },
            { value: "benchmark", label: "Benchmarks" },
          ]}
        />
        <TextInput placeholder="Search" leftSection={<IconSearch size={14} />} value={query} onChange={(event) => setQuery(event.currentTarget.value)} aria-label="Search jobs" />
      </Group>
      <Card padding={0}>
        <Table.ScrollContainer minWidth={760}>
          <Table highlightOnHover verticalSpacing="sm" className="wz-num">
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Job</Table.Th>
                <Table.Th>Title</Table.Th>
                <Table.Th>Status</Table.Th>
                <Table.Th>Result</Table.Th>
                <Table.Th>Duration</Table.Th>
                <Table.Th>Started</Table.Th>
                <Table.Th />
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {list.map((job) => {
                const progress = jobProgress(job);
                const active = isActive(job.status);
                return (
                  <Table.Tr key={job.id} className="wz-table-row" onClick={() => navigate(jobPath(job))}>
                    <Table.Td>
                      <Group gap={6} wrap="nowrap">
                        <KindIcon kind={job.kind} />
                        <Text fw={600} size="sm">
                          {job.label}
                        </Text>
                      </Group>
                    </Table.Td>
                    <Table.Td maw={380}>
                      <Text size="sm" truncate>
                        {job.title}
                      </Text>
                      {active && progress !== null ? <Progress value={progress} size="xs" mt={4} /> : null}
                    </Table.Td>
                    <Table.Td>
                      <JobStatusBadge status={job.status} />
                    </Table.Td>
                    <Table.Td>
                      {job.kind === "benchmark" ? (
                        <Text size="sm">{job.row_count} runs</Text>
                      ) : (
                        <RunStatusBadge status={job.result_status} />
                      )}
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{formatSeconds(duration(job.started_at, job.finished_at))}</Text>
                    </Table.Td>
                    <Table.Td>
                      <Text size="sm">{formatTime(job.created_at)}</Text>
                    </Table.Td>
                    <Table.Td onClick={(event) => event.stopPropagation()}>
                      {active ? (
                        <Tooltip label="Cancel">
                          <ActionIcon variant="subtle" color="red" onClick={() => actions.cancel.mutate(job.id)} aria-label={`Cancel ${job.label}`}>
                            <IconPlayerStop size={16} />
                          </ActionIcon>
                        </Tooltip>
                      ) : (
                        <Tooltip label="Delete">
                          <ActionIcon variant="subtle" color="gray" onClick={() => actions.remove.mutate(job.id)} aria-label={`Delete ${job.label}`}>
                            <IconTrash size={16} />
                          </ActionIcon>
                        </Tooltip>
                      )}
                    </Table.Td>
                  </Table.Tr>
                );
              })}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
        {list.length === 0 ? (
          <Text c="dimmed" ta="center" p="xl">
            No jobs yet.
          </Text>
        ) : null}
      </Card>
    </Stack>
  );
}
