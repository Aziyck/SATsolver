import {
  Alert,
  Badge,
  Button,
  Card,
  Grid,
  Group,
  Loader,
  SegmentedControl,
  Stack,
  Text,
  Title,
  Tooltip,
} from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { IconArrowLeft, IconCirclePlus, IconDice5, IconFileCode, IconPlayerPlay } from "@tabler/icons-react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { sortedJobs, useLive } from "../api/live";
import { useCatalog, useCreateJob, useJob } from "../api/queries";
import type { JobDetail, ProblemSpec, SolverSpec } from "../api/types";
import { EstimateBadge } from "../components/Display";
import { ParamForm } from "../components/fields/ParamForm";
import { JobCard } from "../components/JobsDrawer";
import { ProblemCards, ProblemInfo } from "../components/ProblemPicker";
import { SolveResultPanel } from "../components/SolveResultPanel";
import { SolverPanel, type SolverSettings } from "../components/SolverPanel";
import { AnswerView } from "../components/views/ProblemViews";
import { GraphView } from "../components/views/GraphView";
import { edgesAsText, formatEdges, parseEdges, toggleEdge } from "../lib/edges";
import { defaultValues, visibleValues, type Values } from "../lib/params";
import { usePersistentState } from "../lib/storage";

function initialSolverSettings(solvers: SolverSpec[], timeout: number): SolverSettings {
  return {
    solver: "cdcl",
    options: Object.fromEntries(solvers.map((solver) => [solver.key, defaultValues(solver.fields)])),
    timeout,
    logLevel: "normal",
  };
}

export default function SolvePage() {
  const { problem: problemKey } = useParams();
  const [search, setSearch] = useSearchParams();
  const navigate = useNavigate();
  const catalog = useCatalog().data!;
  const problem = catalog.problems.find((item) => item.key === problemKey);
  const jobParam = Number(search.get("job")) || null;

  const [allValues, setAllValues] = usePersistentState<Record<string, Values>>("wizsat.solve.values", () => ({}));
  const [settings, setSettings] = usePersistentState<SolverSettings>("wizsat.solve.solver", () =>
    initialSolverSettings(catalog.solvers, catalog.defaults.solve_timeout),
  );
  const values = useMemo(() => (problem ? { ...defaultValues(problem.fields), ...(allValues[problem.key] ?? {}) } : {}), [problem, allValues]);
  const setValue = (name: string, value: unknown) => {
    if (!problem) return;
    setAllValues((current) => ({ ...current, [problem.key]: { ...values, [name]: value } }));
    setSubmitErrors({});
  };

  const [submitErrors, setSubmitErrors] = useState<Record<string, string>>({});
  const [view, setView] = useState<"preview" | "result">(jobParam ? "result" : "preview");

  // "Open in Solve" from a benchmark row passes the case parameters as router state.
  const location = useLocation();
  useEffect(() => {
    const state = location.state as { params?: Record<string, unknown> } | null;
    if (!problem || !state?.params) return;
    setAllValues((current) => ({ ...current, [problem.key]: { ...(current[problem.key] ?? {}), ...state.params } }));
    setView("preview");
    navigate(location.pathname, { replace: true, state: null });
  }, [location.state, location.pathname, problem, setAllValues, navigate]);
  useEffect(() => {
    if (jobParam) setView("result");
  }, [jobParam]);

  const payload = useMemo(() => (problem ? visibleValues(problem.fields, values) : {}), [problem, values]);
  const [debouncedPayload] = useDebouncedValue(payload, 350);
  const preview = useQuery({
    queryKey: ["preview", problem?.key, JSON.stringify(debouncedPayload)],
    queryFn: () => api.preview(problem!.key, debouncedPayload),
    enabled: Boolean(problem),
    placeholderData: keepPreviousData,
    retry: false,
  });
  const previewErrors = preview.error instanceof ApiError ? preview.error.errors : {};
  const errors = { ...previewErrors, ...submitErrors };

  const createJob = useCreateJob();
  const submit = (kind: "solve" | "generate") => {
    if (!problem) return;
    const body =
      kind === "solve"
        ? {
            problem: problem.key,
            params: payload,
            solver: settings.solver,
            options: visibleValues(catalog.solvers.find((solver) => solver.key === settings.solver)?.fields ?? [], settings.options[settings.solver] ?? {}),
            timeout: settings.timeout === "" ? null : settings.timeout,
            log_level: settings.logLevel,
          }
        : { problem: problem.key, params: payload };
    createJob.mutate(
      { kind, body },
      {
        onSuccess: (job) => {
          setSubmitErrors({});
          setSearch({ job: String(job.id) });
          setView("result");
        },
        onError: (error) => setSubmitErrors(error instanceof ApiError ? { ...error.errors, _: Object.keys(error.errors).length ? "" : error.message } : { _: String(error) }),
      },
    );
  };

  const editFromJob = (job: JobDetail) => {
    const key = job.problems[0];
    if (!key) return;
    setAllValues((current) => ({ ...current, [key]: { ...(current[key] ?? {}), ...job.request.params } }));
    if (job.request.solver) {
      setSettings((current) => ({
        ...current,
        solver: job.request.solver as string,
        options: { ...current.options, [job.request.solver as string]: { ...(current.options[job.request.solver as string] ?? {}), ...(job.request.options ?? {}) } },
        timeout: job.request.timeout ?? "",
        logLevel: job.request.log_level ?? current.logLevel,
      }));
    }
    setView("preview");
  };

  const openAs = (key: string, params: Record<string, unknown>) => {
    setAllValues((current) => ({ ...current, [key]: { ...(current[key] ?? {}), ...params } }));
    navigate(`/solve/${key}`);
    setView("preview");
  };

  // "Edit" on the full job page (/jobs/:id) sends the job id as router state.
  const editJobId = (location.state as { editJob?: number } | null)?.editJob ?? null;
  const editJob = useJob(editJobId);
  useEffect(() => {
    if (!editJobId || !editJob.data) return;
    editFromJob(editJob.data);
    navigate(location.pathname, { replace: true, state: null });
  }, [editJobId, editJob.data]); // eslint-disable-line react-hooks/exhaustive-deps

  const jobs = useLive((state) => state.jobs);
  const recent = useMemo(
    () => sortedJobs(jobs).filter((job) => job.kind !== "benchmark" && (!problem || job.problems[0] === problem.key)).slice(0, 6),
    [jobs, problem],
  );

  if (!problem) {
    return (
      <Stack gap="lg">
        <div>
          <Title order={2}>What do you want to solve?</Title>
          <Text c="dimmed">
            Pick a problem. WizSAT encodes it as a CNF formula, runs a SAT solver, checks the answer and draws it.
          </Text>
        </div>
        <ProblemCards problems={catalog.problems} onSelect={(key) => navigate(`/solve/${key}`)} />
        {recent.length ? (
          <Stack gap="xs">
            <Title order={4}>Recent runs</Title>
            {recent.map((job) => (
              <JobCard key={job.id} job={job} onOpen={() => navigate(`/solve/${job.problems[0]}?job=${job.id}`)} />
            ))}
          </Stack>
        ) : null}
      </Stack>
    );
  }

  const selectedJob = view === "result" ? jobParam : null;

  return (
    <Stack gap="md">
      <Group justify="space-between" wrap="nowrap">
        <Group gap="xs" wrap="nowrap">
          <Button variant="subtle" px={6} onClick={() => navigate("/solve")} aria-label="All problems" leftSection={<IconArrowLeft size={16} />}>
            Problems
          </Button>
          <Title order={2}>{problem.title}</Title>
          <ProblemInfo problem={problem} />
        </Group>
      </Group>
      <Text c="dimmed" mt={-8}>
        {problem.summary}
      </Text>

      <Grid gutter="lg">
        <Grid.Col span={{ base: 12, md: 5 }}>
          <Stack gap="md">
            <Card>
              <Group justify="space-between" mb="sm">
                <Text fw={650}>Input</Text>
                <EstimateBadge estimate={preview.data?.estimate} tooLarge={preview.data?.too_large} maxClauses={catalog.limits.max_clauses} />
              </Group>
              <ParamForm fields={problem.fields} values={values} onChange={setValue} errors={errors} />
            </Card>
            <Card>
              <Text fw={650} mb="sm">
                Solver
              </Text>
              <SolverPanel solvers={catalog.solvers} settings={settings} onChange={setSettings} errors={submitErrors} />
            </Card>
            {errors._ ? <Alert color="red">{errors._}</Alert> : null}
            <Group grow>
              <Button size="md" leftSection={<IconPlayerPlay size={18} />} onClick={() => submit("solve")} loading={createJob.isPending} disabled={preview.data?.too_large}>
                Solve
              </Button>
              <Tooltip label="Only build the CNF formula, without solving it">
                <Button size="md" variant="default" leftSection={<IconFileCode size={18} />} onClick={() => submit("generate")} disabled={preview.data?.too_large}>
                  Encode only
                </Button>
              </Tooltip>
            </Group>
          </Stack>
        </Grid.Col>

        <Grid.Col span={{ base: 12, md: 7 }}>
          <Stack gap="md" className="wz-sticky">
            <SegmentedControl
              value={view}
              onChange={(next) => setView(next as "preview" | "result")}
              data={[
                { value: "preview", label: "Input preview" },
                { value: "result", label: jobParam ? `Result (J${jobParam})` : "Result", disabled: !jobParam },
              ]}
            />
            {selectedJob ? (
              <SolveResultPanel
                jobId={selectedJob}
                onEdit={editFromJob}
                onOpenAs={openAs}
                onDeleted={() => {
                  setSearch({});
                  setView("preview");
                }}
              />
            ) : (
              <InputPreview problem={problem} values={values} setValue={setValue} preview={preview.data?.preview} loading={preview.isFetching} failed={Boolean(preview.error)} />
            )}
            {recent.length ? (
              <Stack gap="xs">
                <Text fw={650} size="sm">
                  Recent {problem.title} runs
                </Text>
                {recent.map((job) => (
                  <JobCard key={job.id} job={job} onOpen={() => setSearch({ job: String(job.id) })} />
                ))}
              </Stack>
            ) : null}
          </Stack>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}

function InputPreview({
  problem,
  values,
  setValue,
  preview,
  loading,
  failed,
}: {
  problem: ProblemSpec;
  values: Values;
  setValue: (name: string, value: unknown) => void;
  preview: any;
  loading: boolean;
  failed: boolean;
}) {
  const manualGraph = problem.graph_based && values.graph_mode === "manual";
  const randomGraph = problem.graph_based && !manualGraph;
  const edges = manualGraph ? parseEdges(edgesAsText(values.edges)).edges : [];

  return (
    <Card>
      <Group justify="space-between" mb="sm">
        <Group gap="xs">
          <Text fw={650}>Input preview</Text>
          {loading ? <Loader size="xs" /> : null}
        </Group>
        {randomGraph ? (
          <Group gap="xs">
            {preview?.seed !== undefined && values.seed === null ? (
              <Badge variant="light" color="gray">
                random seed {preview.seed}
              </Badge>
            ) : null}
            <Button size="compact-sm" variant="default" leftSection={<IconDice5 size={14} />} onClick={() => setValue("seed", Math.floor(Math.random() * 100000))}>
              New graph
            </Button>
          </Group>
        ) : null}
        {manualGraph ? (
          <Button size="compact-sm" variant="default" leftSection={<IconCirclePlus size={14} />} onClick={() => setValue("nodes", Number(values.nodes) + 1)}>
            Add node
          </Button>
        ) : null}
        {problem.key === "sudoku" && values.source === "generated" ? (
          <Button size="compact-sm" variant="default" leftSection={<IconDice5 size={14} />} onClick={() => setValue("seed", Math.floor(Math.random() * 100000))}>
            New puzzle
          </Button>
        ) : null}
      </Group>
      {manualGraph ? (
        <GraphView
          nodes={Number(values.nodes) || 1}
          edges={edges}
          editable
          onToggleEdge={(u, v) => setValue("edges", formatEdges(toggleEdge(edges, u, v)))}
          height={400}
        />
      ) : failed && !preview ? (
        <Text size="sm" c="dimmed">
          Fix the highlighted inputs to see a preview.
        </Text>
      ) : preview === null ? (
        <Text size="sm" c="dimmed">
          No preview for this problem.
        </Text>
      ) : preview ? (
        problem.key === "n_queens" ? (
          <Stack gap="xs">
            <AnswerView view="queens" visual={preview} decoded={null} />
            <Text size="sm" c="dimmed">
              Place {preview.size} queens so that none shares a row, column or diagonal.
            </Text>
          </Stack>
        ) : (
          <AnswerView view={problem.result_view} visual={preview} decoded={null} />
        )
      ) : (
        <Loader size="sm" />
      )}
      {problem.key === "random_3sat" && preview ? (
        <Text size="sm" c="dimmed" mt="sm">
          {preview.variables} variables, {preview.clauses} clauses, ratio {(preview.clauses / preview.variables).toFixed(2)}.
          Random formulas are hardest near ratio 4.26.
        </Text>
      ) : null}
    </Card>
  );
}
