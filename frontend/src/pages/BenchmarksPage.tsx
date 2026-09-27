import { Badge, Button, Card, Group, SimpleGrid, Stack, Text, Title } from "@mantine/core";
import { IconChartDots, IconPlus } from "@tabler/icons-react";
import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { sortedJobs, useLive } from "../api/live";
import { useCatalog } from "../api/queries";
import { JobCard } from "../components/JobsDrawer";
import { formatCount } from "../lib/format";

export default function BenchmarksPage() {
  const catalog = useCatalog().data!;
  const navigate = useNavigate();
  const jobs = useLive((state) => state.jobs);
  const benchmarks = useMemo(() => sortedJobs(jobs).filter((job) => job.kind === "benchmark"), [jobs]);

  return (
    <Stack gap="lg">
      <Group justify="space-between">
        <div>
          <Title order={2}>Benchmarks</Title>
          <Text c="dimmed">Sweep problem parameters, run several solvers on every instance, and compare them.</Text>
        </div>
        <Button leftSection={<IconPlus size={16} />} onClick={() => navigate("/benchmarks/new")}>
          New benchmark
        </Button>
      </Group>

      <Stack gap="xs">
        <Title order={4}>Start from a preset</Title>
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }} spacing="md">
          {catalog.presets.map((preset) => (
            <Card key={preset.key} padding="md">
              <Stack gap={6} h="100%">
                <Group gap={6}>
                  {preset.tags.map((tag) => (
                    <Badge key={tag} variant="light" size="xs" color={tag === "report" ? "gold" : "wizard"}>
                      {tag}
                    </Badge>
                  ))}
                </Group>
                <Text fw={650}>{preset.title}</Text>
                <Text size="sm" c="dimmed" style={{ flex: 1 }}>
                  {preset.description}
                </Text>
                <Text size="xs" c="dimmed">
                  {formatCount(preset.cases)} cases · {formatCount(preset.runs)} runs
                </Text>
                <Button variant="light" size="xs" onClick={() => navigate(`/benchmarks/new?preset=${preset.key}`)}>
                  Use this preset
                </Button>
              </Stack>
            </Card>
          ))}
        </SimpleGrid>
      </Stack>

      <Stack gap="xs">
        <Title order={4}>Your benchmarks</Title>
        {benchmarks.length === 0 ? (
          <Card padding="xl">
            <Stack align="center" gap="xs">
              <IconChartDots size={40} stroke={1.3} />
              <Text c="dimmed">No benchmarks yet. Start one from a preset or build your own.</Text>
            </Stack>
          </Card>
        ) : (
          <SimpleGrid cols={{ base: 1, md: 2 }} spacing="sm">
            {benchmarks.map((job) => (
              <JobCard key={job.id} job={job} onOpen={() => navigate(`/benchmarks/${job.id}`)} />
            ))}
          </SimpleGrid>
        )}
      </Stack>
    </Stack>
  );
}
