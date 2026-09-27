import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Card,
  Chip,
  Divider,
  Grid,
  Group,
  Loader,
  Menu,
  NumberInput,
  SegmentedControl,
  Select,
  Stack,
  Text,
  TextInput,
  Title,
  Tooltip,
} from "@mantine/core";
import { useDebouncedValue } from "@mantine/hooks";
import { IconArrowLeft, IconCopy, IconPlayerPlay, IconPlus, IconRestore, IconTrash } from "@tabler/icons-react";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import { useCatalog, useCreateJob } from "../api/queries";
import type { Catalog, Rule } from "../api/types";
import { ParamInput } from "../components/fields/ParamForm";
import {
  draftFromRequest,
  emptyDraft,
  isVisibleSweep,
  newId,
  requestFromDraft,
  sweepDefaults,
  unionFields,
  type BenchmarkDraft,
} from "../lib/benchmark";
import { formatCount } from "../lib/format";
import { defaultValues, errorsUnder } from "../lib/params";
import { usePersistentState } from "../lib/storage";
import { ParamForm } from "../components/fields/ParamForm";

export const DRAFT_KEY = "wizsat.benchmark.draft";

export default function BenchmarkBuilder() {
  const catalog = useCatalog().data!;
  const navigate = useNavigate();
  const [search, setSearch] = useSearchParams();
  const [draft, setDraft] = usePersistentState<BenchmarkDraft>(DRAFT_KEY, () => emptyDraft(catalog));

  // ?preset=key loads a preset into the draft once.
  useEffect(() => {
    const presetKey = search.get("preset");
    if (!presetKey) return;
    const preset = catalog.presets.find((item) => item.key === presetKey);
    if (preset) setDraft({ ...draftFromRequest(catalog, preset.request), title: preset.title });
    setSearch({}, { replace: true });
  }, [search, catalog, setDraft, setSearch]);

  const request = useMemo(() => requestFromDraft(catalog, draft), [catalog, draft]);
  const [debounced] = useDebouncedValue(request, 400);
  const plan = useQuery({
    queryKey: ["plan", JSON.stringify(debounced)],
    queryFn: () => api.plan(debounced),
    placeholderData: keepPreviousData,
    retry: false,
  });
  const [submitErrors, setSubmitErrors] = useState<Record<string, string>>({});
  const errors = { ...(plan.error instanceof ApiError ? plan.error.errors : {}), ...submitErrors };
  const createJob = useCreateJob();

  const update = (patch: Partial<BenchmarkDraft>) => {
    setSubmitErrors({});
    setDraft((current) => ({ ...current, ...patch }));
  };

  const start = () =>
    createJob.mutate(
      { kind: "benchmark", body: request, title: draft.title || undefined },
      {
        onSuccess: (job) => navigate(`/benchmarks/${job.id}`),
        onError: (error) => setSubmitErrors(error instanceof ApiError ? { ...error.errors, _: error.message } : { _: String(error) }),
      },
    );

  return (
    <Stack gap="md">
      <Group justify="space-between">
        <Group gap="xs">
          <Button variant="subtle" px={6} leftSection={<IconArrowLeft size={16} />} onClick={() => navigate("/benchmarks")}>
            Benchmarks
          </Button>
          <Title order={2}>New benchmark</Title>
        </Group>
        <Group gap="xs">
          <Menu position="bottom-end" width={320}>
            <Menu.Target>
              <Button variant="default">Load a preset</Button>
            </Menu.Target>
            <Menu.Dropdown>
              {catalog.presets.map((preset) => (
                <Menu.Item key={preset.key} onClick={() => setDraft({ ...draftFromRequest(catalog, preset.request), title: preset.title })}>
                  <Text size="sm" fw={600}>
                    {preset.title}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {preset.cases} cases, {preset.runs} runs
                  </Text>
                </Menu.Item>
              ))}
            </Menu.Dropdown>
          </Menu>
          <Tooltip label="Start over with defaults">
            <ActionIcon variant="default" size="lg" onClick={() => setDraft(emptyDraft(catalog))} aria-label="Reset the form">
              <IconRestore size={18} />
            </ActionIcon>
          </Tooltip>
        </Group>
      </Group>

      <Grid gutter="lg">
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <Stack gap="md">
            <Card>
              <Stack gap="sm">
                <TextInput label="Name" placeholder="Optional, e.g. 'Phase transition, n=50'" value={draft.title} onChange={(event) => update({ title: event.currentTarget.value })} />
                <ProblemChooser catalog={catalog} draft={draft} onChange={update} error={errors.problems} />
              </Stack>
            </Card>

            {draft.segments.map((segment, index) => (
              <SegmentCard
                key={index}
                catalog={catalog}
                draft={draft}
                index={index}
                errors={errorsUnder(errors, `segments.${index}`)}
                onChange={(values) => update({ segments: draft.segments.map((item, i) => (i === index ? values : item)) })}
                onRemove={draft.segments.length > 1 ? () => update({ segments: draft.segments.filter((_, i) => i !== index) }) : undefined}
                onDuplicate={() => update({ segments: [...draft.segments.slice(0, index + 1), { ...segment }, ...draft.segments.slice(index + 1)] })}
              />
            ))}
            <Button
              variant="light"
              leftSection={<IconPlus size={16} />}
              onClick={() => update({ segments: [...draft.segments, sweepDefaults(unionFields(catalog, draft.problems))] })}
              style={{ alignSelf: "flex-start" }}
            >
              Add another parameter grid
            </Button>

            <SolversCard catalog={catalog} draft={draft} onChange={update} errors={errors} />
            <SettingsCard catalog={catalog} draft={draft} onChange={update} errors={errors} />
          </Stack>
        </Grid.Col>

        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Card className="wz-sticky">
            <Stack gap="sm">
              <Group justify="space-between">
                <Text fw={650}>Plan</Text>
                {plan.isFetching ? <Loader size="xs" /> : null}
              </Group>
              {plan.data && !plan.error ? (
                <>
                  <div>
                    <Text size="xs" c="dimmed">
                      Solver runs
                    </Text>
                    <Text fw={700} fz={36} lh={1.1}>
                      {formatCount(plan.data.runs)}
                    </Text>
                    <Text size="sm" c="dimmed">
                      {formatCount(plan.data.cases)} cases x {plan.data.solvers.length} solver{plan.data.solvers.length === 1 ? "" : "s"}
                    </Text>
                  </div>
                  {plan.data.largest ? (
                    <Text size="sm">
                      Largest formula: ~{formatCount(plan.data.largest.variables)} variables, {formatCount(plan.data.largest.clauses)} clauses
                    </Text>
                  ) : null}
                  <Group gap={4}>
                    {plan.data.solvers.map((label) => (
                      <Badge key={label} variant="light" size="sm">
                        {label}
                      </Badge>
                    ))}
                  </Group>
                  {plan.data.rules.length ? (
                    <Stack gap={2}>
                      <Text size="xs" c="dimmed">
                        Limits
                      </Text>
                      {plan.data.rules.map((rule) => (
                        <Text key={rule} size="sm">
                          {rule}
                        </Text>
                      ))}
                    </Stack>
                  ) : null}
                  <Divider />
                  <Text size="xs" c="dimmed">
                    First cases
                  </Text>
                  <Stack gap={2}>
                    {plan.data.sample.slice(0, 8).map((item, index) => (
                      <Text key={index} size="xs" className="wz-mono" truncate>
                        {draft.problems.length > 1 ? `${item.problem}: ` : ""}
                        {item.label}
                        {item.repeat > 1 ? ` (repeat ${item.repeat})` : ""}
                      </Text>
                    ))}
                    {plan.data.cases > 8 ? (
                      <Text size="xs" c="dimmed">
                        ... and {formatCount(plan.data.cases - 8)} more
                      </Text>
                    ) : null}
                  </Stack>
                </>
              ) : plan.error ? (
                <Alert color="red" variant="light" title="Fix the highlighted fields">
                  {plan.error instanceof ApiError ? plan.error.message : String(plan.error)}
                </Alert>
              ) : (
                <Loader size="sm" />
              )}
              {submitErrors._ ? <Alert color="red">{submitErrors._}</Alert> : null}
              <Button size="md" leftSection={<IconPlayerPlay size={18} />} onClick={start} loading={createJob.isPending} disabled={Boolean(plan.error)}>
                Start benchmark
              </Button>
              <Text size="xs" c="dimmed">
                Runs in the background; you can leave this page. Results stream in live.
              </Text>
            </Stack>
          </Card>
        </Grid.Col>
      </Grid>
    </Stack>
  );
}

function ProblemChooser({
  catalog,
  draft,
  onChange,
  error,
}: {
  catalog: Catalog;
  draft: BenchmarkDraft;
  onChange: (patch: Partial<BenchmarkDraft>) => void;
  error?: string;
}) {
  const setProblems = (next: string[]) => {
    if (!next.length) return;
    const added = next.find((key) => !draft.problems.includes(key));
    const spec = catalog.problems.find((problem) => problem.key === added);
    // Several problems only make sense for graph problems (they share the graphs).
    let problems = next;
    if (spec && !spec.graph_based) problems = [spec.key];
    else if (spec) problems = next.filter((key) => catalog.problems.find((problem) => problem.key === key)?.graph_based);
    const fields = unionFields(catalog, problems);
    const segments = draft.segments.map((values) => ({ ...sweepDefaults(fields), ...Object.fromEntries(Object.entries(values).filter(([name]) => fields.some((field) => field.name === name))) }));
    onChange({ problems, segments });
  };
  return (
    <Stack gap={6}>
      <Text size="sm" fw={500}>
        Problem
      </Text>
      <Chip.Group multiple value={draft.problems} onChange={setProblems}>
        <Group gap={6}>
          {catalog.problems.map((problem) => (
            <Chip key={problem.key} value={problem.key} variant="light">
              {problem.title}
            </Chip>
          ))}
        </Group>
      </Chip.Group>
      <Text size="xs" c={error ? "red" : "dimmed"}>
        {error ||
          (draft.problems.length > 1
            ? "Graph suite: every selected problem runs on exactly the same graphs."
            : "Select several graph problems to compare them on the same graphs.")}
      </Text>
    </Stack>
  );
}

function SegmentCard({
  catalog,
  draft,
  index,
  errors,
  onChange,
  onRemove,
  onDuplicate,
}: {
  catalog: Catalog;
  draft: BenchmarkDraft;
  index: number;
  errors: Record<string, string>;
  onChange: (values: Record<string, unknown>) => void;
  onRemove?: () => void;
  onDuplicate: () => void;
}) {
  const fields = unionFields(catalog, draft.problems);
  const values = draft.segments[index];
  const visible = fields.filter((field) => isVisibleSweep(field, values));
  return (
    <Card>
      <Group justify="space-between" mb="sm">
        <div>
          <Text fw={650}>{draft.segments.length > 1 ? `Parameter grid ${index + 1}` : "Parameters"}</Text>
          <Text size="xs" c="dimmed">
            Comma-separated lists and ranges (1..20, 0.1..0.5:0.1) become one case per combination.
          </Text>
        </div>
        <Group gap={4}>
          <Tooltip label="Duplicate this grid">
            <ActionIcon variant="subtle" onClick={onDuplicate} aria-label="Duplicate grid">
              <IconCopy size={16} />
            </ActionIcon>
          </Tooltip>
          {onRemove ? (
            <Tooltip label="Remove this grid">
              <ActionIcon variant="subtle" color="red" onClick={onRemove} aria-label="Remove grid">
                <IconTrash size={16} />
              </ActionIcon>
            </Tooltip>
          ) : null}
        </Group>
      </Group>
      <Grid gutter="sm">
        {visible.map((field) => (
          <Grid.Col key={field.name} span={{ base: 12, sm: field.kind === "cnf" || field.kind === "edges" || field.kind === "sudoku_grid" || field.kind === "choice" ? 12 : 6 }}>
            <ParamInput field={field} value={values[field.name]} values={values} onChange={(name, value) => onChange({ ...values, [name]: value })} error={errors[field.name]} sweep />
          </Grid.Col>
        ))}
      </Grid>
    </Card>
  );
}

function SolversCard({
  catalog,
  draft,
  onChange,
  errors,
}: {
  catalog: Catalog;
  draft: BenchmarkDraft;
  onChange: (patch: Partial<BenchmarkDraft>) => void;
  errors: Record<string, string>;
}) {
  const add = (solver: string) => {
    const spec = catalog.solvers.find((item) => item.key === solver)!;
    onChange({ solvers: [...draft.solvers, { id: newId(), solver, options: defaultValues(spec.fields), label: "" }] });
  };
  return (
    <Card>
      <Group justify="space-between" mb="sm">
        <div>
          <Text fw={650}>Solvers</Text>
          <Text size="xs" c="dimmed">
            Every case runs with every solver. Add the same solver twice to compare its options.
          </Text>
        </div>
        <Menu>
          <Menu.Target>
            <Button variant="light" size="xs" leftSection={<IconPlus size={14} />}>
              Add solver
            </Button>
          </Menu.Target>
          <Menu.Dropdown>
            {catalog.solvers.map((solver) => (
              <Menu.Item key={solver.key} onClick={() => add(solver.key)}>
                <Text size="sm" fw={600}>
                  {solver.title}
                </Text>
                <Text size="xs" c="dimmed">
                  {solver.complete ? "complete" : "incomplete (local search)"}
                </Text>
              </Menu.Item>
            ))}
          </Menu.Dropdown>
        </Menu>
      </Group>
      {errors.solvers ? (
        <Text size="sm" c="red" mb="xs">
          {errors.solvers}
        </Text>
      ) : null}
      <Stack gap="sm">
        {draft.solvers.map((entry, index) => {
          const spec = catalog.solvers.find((solver) => solver.key === entry.solver)!;
          const setEntry = (patch: Partial<typeof entry>) =>
            onChange({ solvers: draft.solvers.map((item) => (item.id === entry.id ? { ...item, ...patch } : item)) });
          return (
            <Card key={entry.id} withBorder radius="md" padding="sm">
              <Group justify="space-between" mb={spec.fields.length ? "xs" : 0} wrap="nowrap">
                <Group gap="xs" wrap="nowrap">
                  <Badge variant="light">{spec.title}</Badge>
                  <TextInput
                    size="xs"
                    placeholder="Label (optional)"
                    value={entry.label}
                    onChange={(event) => setEntry({ label: event.currentTarget.value })}
                    aria-label="Solver label"
                  />
                </Group>
                <ActionIcon
                  variant="subtle"
                  color="red"
                  onClick={() => onChange({ solvers: draft.solvers.filter((item) => item.id !== entry.id) })}
                  aria-label={`Remove ${spec.title}`}
                  disabled={draft.solvers.length === 1}
                >
                  <IconTrash size={16} />
                </ActionIcon>
              </Group>
              {spec.fields.length ? (
                <ParamForm
                  fields={spec.fields}
                  values={entry.options}
                  errors={errorsUnder(errors, `solvers.${index}.options`)}
                  onChange={(name, value) => setEntry({ options: { ...entry.options, [name]: value } })}
                />
              ) : (
                <Text size="xs" c="dimmed" mt={4}>
                  No options.
                </Text>
              )}
            </Card>
          );
        })}
      </Stack>
    </Card>
  );
}

function SettingsCard({
  catalog,
  draft,
  onChange,
  errors,
}: {
  catalog: Catalog;
  draft: BenchmarkDraft;
  onChange: (patch: Partial<BenchmarkDraft>) => void;
  errors: Record<string, string>;
}) {
  const setRule = (index: number, patch: Partial<Rule>) => onChange({ rules: draft.rules.map((rule, i) => (i === index ? { ...rule, ...patch } : rule)) });
  const solverOptions = [{ value: "*", label: "Any solver" }, ...catalog.solvers.map((solver) => ({ value: solver.key, label: solver.title }))];
  return (
    <Card>
      <Text fw={650} mb="sm">
        Run settings
      </Text>
      <Grid gutter="sm">
        <Grid.Col span={{ base: 6, sm: 3 }}>
          <NumberInput label="Repeats" description="Runs per case" min={1} max={1000} value={draft.repeats} onChange={(repeats) => onChange({ repeats })} error={errors.repeats} />
        </Grid.Col>
        <Grid.Col span={{ base: 6, sm: 3 }}>
          <NumberInput label="Time limit (s)" description="Per run; blank = none" min={0} value={draft.timeout} onChange={(timeout) => onChange({ timeout })} error={errors.timeout} />
        </Grid.Col>
        <Grid.Col span={{ base: 6, sm: 3 }}>
          <NumberInput label="Seed" description="Used where a grid has no seed" min={0} allowDecimal={false} value={draft.seed} onChange={(seed) => onChange({ seed })} error={errors.seed} />
        </Grid.Col>
        <Grid.Col span={{ base: 6, sm: 3 }}>
          <Select
            label="Log detail"
            description="Solver messages"
            data={[
              { value: "normal", label: "Normal" },
              { value: "periodic", label: "Progress" },
              { value: "debug", label: "Debug" },
            ]}
            value={draft.logLevel}
            onChange={(logLevel) => logLevel && onChange({ logLevel })}
            allowDeselect={false}
          />
        </Grid.Col>
      </Grid>
      <Text size="xs" c="dimmed" mt="xs">
        Repeat 1 uses each case's own seed, so any row can be reproduced on the Solve page; later repeats derive fresh seeds.
      </Text>

      <Divider my="md" />
      <Group justify="space-between" mb="xs">
        <div>
          <Text fw={600} size="sm">
            Limit rules
          </Text>
          <Text size="xs" c="dimmed">
            Cap the time of, or skip, a solver once a formula has at least N variables. The first rule is the DPLL fallback.
          </Text>
        </div>
        <Button
          variant="light"
          size="xs"
          leftSection={<IconPlus size={14} />}
          onClick={() => onChange({ rules: [...draft.rules, { solver: "dpll", action: "cap", min_variables: 200, seconds: 10 }] })}
        >
          Add rule
        </Button>
      </Group>
      <Stack gap="xs">
        {draft.rules.length === 0 ? (
          <Text size="sm" c="dimmed">
            No rules: every run uses the time limit above.
          </Text>
        ) : null}
        {draft.rules.map((rule, index) => {
          const ruleErrors = errorsUnder(errors, `rules.${index}`);
          return (
            <Group key={index} gap="xs" align="flex-end" wrap="wrap">
              <Select size="xs" w={130} label={index === 0 ? "Solver" : undefined} data={solverOptions} value={rule.solver} onChange={(solver) => solver && setRule(index, { solver })} allowDeselect={false} aria-label="Rule solver" />
              <SegmentedControl
                size="xs"
                value={rule.action}
                onChange={(action) => setRule(index, { action: action as Rule["action"], seconds: action === "cap" ? (rule.seconds ?? 10) : null })}
                data={[
                  { value: "cap", label: "Cap time" },
                  { value: "skip", label: "Skip" },
                ]}
              />
              {rule.action === "cap" ? (
                <NumberInput size="xs" w={110} label={index === 0 ? "Seconds" : undefined} min={0} value={rule.seconds ?? ""} onChange={(seconds) => setRule(index, { seconds: seconds === "" ? null : Number(seconds) })} error={ruleErrors.seconds} aria-label="Cap seconds" />
              ) : null}
              <NumberInput
                size="xs"
                w={150}
                label={index === 0 ? "When variables >=" : undefined}
                min={0}
                value={rule.min_variables}
                onChange={(value) => setRule(index, { min_variables: Number(value) || 0 })}
                aria-label="Minimum variables"
              />
              <ActionIcon variant="subtle" color="red" onClick={() => onChange({ rules: draft.rules.filter((_, i) => i !== index) })} aria-label="Remove rule">
                <IconTrash size={16} />
              </ActionIcon>
            </Group>
          );
        })}
      </Stack>
    </Card>
  );
}
