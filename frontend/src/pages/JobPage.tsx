import { Alert, Button, Group, Loader, Stack } from "@mantine/core";
import { IconArrowLeft, IconWand } from "@tabler/icons-react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import { useJob } from "../api/queries";
import type { JobDetail } from "../api/types";
import { SolveResultPanel } from "../components/SolveResultPanel";

/**
 * Full page for a solve or encode job (/jobs/:id), the counterpart of the
 * benchmark results page: the same result panel, full width, with a large
 * live log. Benchmarks redirect to their own page.
 */
export default function JobPage() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const { data: job, isLoading, isError } = useJob(id);

  if (isLoading) return <Loader />;
  if (isError || !job) {
    return (
      <Alert color="gray" title="Job not found">
        This job was deleted.
      </Alert>
    );
  }
  if (job.kind === "benchmark") return <Navigate to={`/benchmarks/${job.id}`} replace />;

  const problem = job.problems[0] ?? "";
  // Edit and "open as" hand the parameters to the Solve page through router
  // state, the same way "Open in Solve" does for a benchmark row.
  const edit = (detail: JobDetail) => navigate(`/solve/${problem}`, { state: { editJob: detail.id } });
  const openAs = (key: string, params: Record<string, unknown>) => navigate(`/solve/${key}`, { state: { params } });

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Button variant="subtle" px={6} leftSection={<IconArrowLeft size={16} />} onClick={() => navigate("/jobs")}>
          Jobs
        </Button>
        <Button variant="default" leftSection={<IconWand size={16} />} onClick={() => navigate(`/solve/${problem}?job=${job.id}`)}>
          Show on the Solve page
        </Button>
      </Group>
      <SolveResultPanel jobId={job.id} layout="page" onEdit={edit} onOpenAs={openAs} onDeleted={() => navigate("/jobs")} />
    </Stack>
  );
}
