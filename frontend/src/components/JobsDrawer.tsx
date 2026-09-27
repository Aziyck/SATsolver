import { ActionIcon, Badge, Button, Drawer, Group, Indicator, Progress, ScrollArea, Stack, Text, Tooltip, UnstyledButton } from "@mantine/core";
import { useDisclosure } from "@mantine/hooks";
import { IconChartLine, IconCpu, IconFileCode, IconPlayerStop, IconStack2 } from "@tabler/icons-react";
import { useNavigate } from "react-router-dom";
import { sortedJobs, useLive } from "../api/live";
import { useJobActions } from "../api/queries";
import type { JobSummary } from "../api/types";
import { formatSeconds, formatTime } from "../lib/format";
import { isActive, JobStatusBadge, RunStatusBadge } from "../lib/status";

export function jobPath(job: Pick<JobSummary, "id" | "kind" | "problems">): string {
  if (job.kind === "benchmark") return `/benchmarks/${job.id}`;
  return `/solve/${job.problems[0] ?? ""}?job=${job.id}`;
}

export function jobProgress(job: JobSummary): number | null {
  const { current, total } = job.progress;
  if (!total) return null;
  return Math.min(100, ((current ?? 0) / total) * 100);
}

export function KindIcon({ kind, size = 16 }: { kind: JobSummary["kind"]; size?: number }) {
  if (kind === "benchmark") return <IconChartLine size={size} />;
  if (kind === "generate") return <IconFileCode size={size} />;
  return <IconCpu size={size} />;
}

export function JobCard({ job, onOpen }: { job: JobSummary; onOpen: () => void }) {
  const { cancel } = useJobActions();
  const progress = jobProgress(job);
  const active = isActive(job.status);
  return (
    <UnstyledButton
      onClick={onOpen}
      p="sm"
      style={{ borderRadius: "var(--mantine-radius-md)", border: "1px solid var(--wz-hairline)" }}
      aria-label={`Open ${job.label}`}
    >
      <Group justify="space-between" wrap="nowrap" gap="xs">
        <Group gap={8} wrap="nowrap" style={{ minWidth: 0 }}>
          <KindIcon kind={job.kind} />
          <Text fw={600} size="sm">
            {job.label}
          </Text>
          <Text size="sm" truncate>
            {job.title}
          </Text>
        </Group>
        {active ? (
          <Tooltip label="Cancel">
            <ActionIcon
              variant="subtle"
              color="red"
              aria-label={`Cancel ${job.label}`}
              onClick={(event) => {
                event.stopPropagation();
                cancel.mutate(job.id);
              }}
            >
              <IconPlayerStop size={16} />
            </ActionIcon>
          </Tooltip>
        ) : null}
      </Group>
      <Group gap="xs" mt={6}>
        <JobStatusBadge status={job.status} />
        {job.result_status ? <RunStatusBadge status={job.result_status} /> : null}
        {job.kind === "benchmark" && job.row_count ? (
          <Badge variant="default" radius="sm">
            {job.row_count} runs
          </Badge>
        ) : null}
        {job.elapsed !== null ? (
          <Text size="xs" c="dimmed">
            {formatSeconds(job.elapsed)}
          </Text>
        ) : null}
        <Text size="xs" c="dimmed" ml="auto">
          {formatTime(job.created_at)}
        </Text>
      </Group>
      {active && progress !== null ? <Progress value={progress} size="sm" mt={8} animated={job.status === "running"} /> : null}
      {job.error && job.status === "failed" ? (
        <Text size="xs" c="red" mt={4} lineClamp={2}>
          {job.error}
        </Text>
      ) : null}
    </UnstyledButton>
  );
}

export function JobsDrawer({ activeCount }: { activeCount: number }) {
  const [opened, { open, close }] = useDisclosure(false);
  const jobs = useLive((state) => state.jobs);
  const navigate = useNavigate();
  const list = sortedJobs(jobs).slice(0, 40);

  return (
    <>
      <Indicator label={activeCount} size={16} disabled={activeCount === 0} offset={4}>
        <Button variant="default" leftSection={<IconStack2 size={16} />} onClick={open} aria-label="Show jobs">
          Jobs
        </Button>
      </Indicator>
      <Drawer opened={opened} onClose={close} position="right" size="md" title={<Text fw={650}>Recent jobs</Text>}>
        <ScrollArea h="calc(100vh - 120px)">
          <Stack gap="xs">
            {list.length === 0 ? (
              <Text c="dimmed" size="sm">
                Nothing has run yet. Solve a problem or start a benchmark and it will show up here.
              </Text>
            ) : (
              list.map((job) => (
                <JobCard
                  key={job.id}
                  job={job}
                  onOpen={() => {
                    close();
                    navigate(jobPath(job));
                  }}
                />
              ))
            )}
            <Button
              variant="subtle"
              onClick={() => {
                close();
                navigate("/jobs");
              }}
            >
              All jobs
            </Button>
          </Stack>
        </ScrollArea>
      </Drawer>
    </>
  );
}
