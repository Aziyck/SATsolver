import {
  Alert,
  Badge,
  Button,
  Card,
  Drawer,
  Group,
  Loader,
  MultiSelect,
  Paper,
  Progress,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Tabs,
  Text,
  TextInput,
  Title,
  Tooltip,
  UnstyledButton,
} from "@mantine/core";
import {
  IconAlertTriangle,
  IconArrowLeft,
  IconChartLine,
  IconChevronDown,
  IconChevronUp,
  IconCopy,
  IconDownload,
  IconListDetails,
  IconSettings,
  IconPlayerSkipForward,
  IconPlayerStop,
  IconRefresh,
  IconSearch,
  IconTable,
  IconTrash,
  IconWand,
} from "@tabler/icons-react";
import { useQueries, useQuery } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, urls } from "../api/client";
import { sortedJobs, useLive } from "../api/live";
import { useCatalog, useJob, useJobActions, useRows } from "../api/queries";
import type { BenchmarkRequest, BenchmarkRow, Catalog } from "../api/types";
import {
  AggregateTable,
  CASE_X,
  FacetedCharts,
  StatusLegendNote,
  StatusShareChart,
  type ChartSettings,
} from "../components/charts/BenchmarkCharts";
import { BenchmarkSetup, entryForRow } from "../components/BenchmarkSetup";
import { FactsList, LogViewer, StatTile } from "../components/Display";
import { SolverSettingsTable, StatsTable } from "../components/SolverSettingsTable";
import { AnswerView } from "../components/views/ProblemViews";
import { draftFromRequest } from "../lib/benchmark";
import { duration, formatCount, formatSeconds, formatStat } from "../lib/format";
import { formatValue } from "../lib/params";
import { METRICS, statusCounts, suspiciousRows, varyingParams, type Aggregate, type Metric } from "../lib/stats";
import { isActive, JobStatusBadge, RunStatusBadge } from "../lib/status";
import { DRAFT_KEY } from "./BenchmarkBuilder";

const PREFERRED_X = ["ratio", "probability", "average_degree", "edge_count", "givens", "variables", "nodes", "size", "target", "colors", "sat_percent"];

export default function BenchmarkResults() {
  const { id } = useParams();
  const jobId = Number(id);
  const navigate = useNavigate();
  const catalog = useCatalog().data!;
  const { data: job, isLoading, isError } = useJob(jobId);
  const rowsQuery = useRows(jobId);
  const actions = useJobActions();
  const liveJobs = useLive((state) => state.jobs);
  const [compare, setCompare] = useState<string[]>([]);
  const [tab, setTab] = useState<string | null>("charts");
  const [selectedRow, setSelectedRow] = useState<BenchmarkRow | null>(null);

  const otherBenchmarks = useMemo(
    () => sortedJobs(liveJobs).filter((item) => item.kind === "benchmark" && item.id !== jobId),
    [liveJobs, jobId],
  );
  const compareQueries = useQueries({
    queries: compare.map((compareId) => ({ queryKey: ["rows", Number(compareId)], queryFn: () => api.rows(Number(compareId)) })),
  });

  const ownRows = useMemo(() => (rowsQuery.data?.rows ?? []).map((row) => ({ ...row, run_label: job?.label ?? "" })), [rowsQuery.data, job?.label]);
  const compareRows = compareQueries.flatMap((query) => (query.data ? query.data.rows.map((row) => ({ ...row, run_label: query.data!.label })) : []));
  const comparing = compare.length > 0;
  const suite = new Set(ownRows.map((row) => row.problem)).size > 1;
  const rows = useMemo(() => {
    const combined = [...ownRows, ...compareRows];
    // Expose "problem" (graph suites) and "run" (comparisons) as chartable parameters.
    return combined.map((row) => ({
      ...row,
      params: { ...row.params, ...(suite ? { problem: row.problem } : {}), ...(comparing ? { run: row.run_label } : {}) },
    }));
  }, [ownRows, compareQueries.map((query) => query.dataUpdatedAt).join(","), suite, comparing]);

  if (isLoading) return <Loader />;
  if (isError || !job) {
    return (
      <Alert color="gray" title="Benchmark not found">
        It may have been deleted.
      </Alert>
    );
  }

  const active = isActive(job.status);
  const total = job.progress.total ?? 0;
  const done = job.row_count;
  const counts = statusCounts(ownRows);
  const suspicious = suspiciousRows(ownRows);
  const solverTime = ownRows.reduce((sum, row) => sum + row.elapsed, 0);

  const editAsNew = () => {
    try {
      window.localStorage.setItem(DRAFT_KEY, JSON.stringify({ ...draftFromRequest(catalog, job.request), title: `${job.title} (copy)` }));
    } catch {
      // ignore storage errors
    }
    navigate("/benchmarks/new");
  };

  return (
    <Stack gap="md">
      <Group justify="space-between" align="flex-start">
        <Stack gap={4}>
          <Group gap="xs">
            <Button variant="subtle" px={6} leftSection={<IconArrowLeft size={16} />} onClick={() => navigate("/benchmarks")}>
              Benchmarks
            </Button>
            <Text c="dimmed" fw={600}>
              {job.label}
            </Text>
            <JobStatusBadge status={job.status} />
          </Group>
          <Title order={2}>{job.title}</Title>
        </Stack>
        <Group gap="xs">
          {active ? (
            <>
              <Tooltip label="Mark the current case as SKIPPED and continue">
                <Button variant="default" leftSection={<IconPlayerSkipForward size={16} />} onClick={() => actions.skip.mutate(job.id)}>
                  Skip case
                </Button>
              </Tooltip>
              <Button color="red" variant="light" leftSection={<IconPlayerStop size={16} />} onClick={() => actions.cancel.mutate(job.id)}>
                Stop
              </Button>
            </>
          ) : (
            <>
              <Button variant="default" leftSection={<IconRefresh size={16} />} onClick={() => actions.rerun.mutate(job.id, { onSuccess: (next) => navigate(`/benchmarks/${next.id}`) })}>
                Rerun
              </Button>
              <Button variant="default" leftSection={<IconCopy size={16} />} onClick={editAsNew}>
                Edit as new
              </Button>
            </>
          )}
          <Button
            component="a"
            href={comparing ? urls.exportMany([jobId, ...compare.map(Number)]) : urls.exportCsv(jobId)}
            variant="light"
            leftSection={<IconDownload size={16} />}
            disabled={!done}
          >
            CSV
          </Button>
          {!active ? (
            <Tooltip label="Delete this benchmark and its results">
              <Button variant="subtle" color="red" aria-label="Delete benchmark" onClick={() => actions.remove.mutate(job.id, { onSuccess: () => navigate("/benchmarks") })}>
                <IconTrash size={16} />
              </Button>
            </Tooltip>
          ) : null}
        </Group>
      </Group>

      {active ? (
        <Card padding="md">
          <Group justify="space-between" mb={6}>
            <Text size="sm">
              {job.status === "queued" ? "Waiting for a free worker..." : `${formatCount(done)} of ${formatCount(total)} runs`}
            </Text>
            <Text size="sm" c="dimmed">
              {formatSeconds(duration(job.started_at, null))}
            </Text>
          </Group>
          <Progress value={total ? (done / total) * 100 : 0} size="lg" animated striped />
        </Card>
      ) : null}
      {job.status === "failed" ? (
        <Alert color="red" title="The benchmark failed" icon={<IconAlertTriangle />}>
          {job.error}
        </Alert>
      ) : null}

      <SimpleGrid cols={{ base: 2, sm: 3, lg: 6 }} spacing="sm">
        <StatTile label="Runs" value={`${formatCount(done)}${total ? ` / ${formatCount(total)}` : ""}`} />
        <StatTile label="SAT" value={formatCount(counts.SAT ?? 0)} />
        <StatTile label="UNSAT" value={formatCount(counts.UNSAT ?? 0)} />
        <StatTile label="No answer" value={formatCount((counts.UNKNOWN ?? 0) + (counts.TIMEOUT ?? 0))} hint="UNKNOWN + TIMEOUT" />
        <StatTile label="Skipped / errors" value={`${formatCount(counts.SKIPPED ?? 0)} / ${formatCount(counts.ERROR ?? 0)}`} />
        <StatTile label="Solver time" value={formatSeconds(solverTime)} />
      </SimpleGrid>

      {suspicious.length ? (
        <Alert color="red" icon={<IconAlertTriangle />} title={`${suspicious.length} suspicious result${suspicious.length > 1 ? "s" : ""}`}>
          A model failed verification or an answer contradicts the generator's guarantee (for example UNSAT on a planted SAT formula).
          Open them in the Runs tab.
        </Alert>
      ) : null}

      <Group gap="xs" align="flex-end">
        <MultiSelect
          label="Compare with other benchmarks"
          placeholder={otherBenchmarks.length ? "Add runs to overlay" : "No other benchmarks yet"}
          data={otherBenchmarks.map((item) => ({ value: String(item.id), label: `${item.label}: ${item.title}` }))}
          value={compare}
          onChange={setCompare}
          clearable
          searchable
          style={{ flex: 1, maxWidth: 560 }}
        />
      </Group>

      <Tabs value={tab} onChange={setTab} keepMounted={false}>
        <Tabs.List>
          <Tabs.Tab value="charts" leftSection={<IconChartLine size={16} />}>
            Charts
          </Tabs.Tab>
          <Tabs.Tab value="runs" leftSection={<IconTable size={16} />}>
            Runs ({formatCount(rows.length)})
          </Tabs.Tab>
          <Tabs.Tab value="setup" leftSection={<IconSettings size={16} />}>
            Setup
          </Tabs.Tab>
          <Tabs.Tab value="log" leftSection={<IconListDetails size={16} />}>
            Log
          </Tabs.Tab>
        </Tabs.List>
        <Tabs.Panel value="charts" pt="md">
          {rows.length ? <ChartsPanel rows={rows} comparing={comparing} /> : <EmptyRows active={active} />}
        </Tabs.Panel>
        <Tabs.Panel value="runs" pt="md">
          {rows.length ? <RunsTable rows={rows} catalog={catalog} showRun={comparing} showProblem={suite} onSelect={setSelectedRow} /> : <EmptyRows active={active} />}
        </Tabs.Panel>
        <Tabs.Panel value="setup" pt="md">
          <BenchmarkSetup request={job.request} catalog={catalog} />
        </Tabs.Panel>
        <Tabs.Panel value="log" pt="md">
          <LogViewer jobId={jobId} initial={job.logs} height={480} />
        </Tabs.Panel>
      </Tabs>

      <RowDrawer row={selectedRow} jobId={jobId} request={job.request} catalog={catalog} onClose={() => setSelectedRow(null)} />
    </Stack>
  );
}

function EmptyRows({ active }: { active: boolean }) {
  return (
    <Paper withBorder p="xl" radius="md">
      <Text c="dimmed" ta="center">
        {active ? "Results appear here as soon as the first run finishes." : "This benchmark produced no rows."}
      </Text>
    </Paper>
  );
}

function ChartsPanel({ rows, comparing }: { rows: BenchmarkRow[]; comparing: boolean }) {
  const varying = useMemo(() => varyingParams(rows), [rows]);
  const numeric = varying.filter((item) => item.numeric);
  const defaultX = useMemo(() => {
    const preferred = PREFERRED_X.find((name) => numeric.some((item) => item.name === name));
    return preferred ?? numeric[0]?.name ?? varying[0]?.name ?? CASE_X;
  }, [numeric, varying]);
  const defaultFacet = useMemo(() => {
    const facet =
      varying.find((item) => item.name === "problem")?.name ??
      varying.find((item) => item.name !== defaultX && item.name !== "seed" && item.values.length <= 6)?.name ??
      null;
    return facet === defaultX ? null : facet;
  }, [varying, defaultX]);
  const [settings, setSettings] = useState<ChartSettings>({ x: defaultX, facet: defaultFacet, metric: "elapsed", aggregate: "median", log: false });
  const [shareSeries, setShareSeries] = useState<string | null>(null);

  useEffect(() => {
    // Rows stream in live: adopt sensible defaults until the chosen axis exists.
    setSettings((current) =>
      current.x !== CASE_X && varying.some((item) => item.name === current.x) ? current : { ...current, x: defaultX, facet: defaultFacet },
    );
  }, [defaultX, defaultFacet, varying]);

  const seriesOf = useCallback((row: BenchmarkRow) => (comparing ? `${row.run_label} ${row.solver_label}` : row.solver_label), [comparing]);
  const seriesOrder = useMemo(() => {
    const order: string[] = [];
    rows.forEach((row) => {
      const key = seriesOf(row);
      if (!order.includes(key)) order.push(key);
    });
    return order;
  }, [rows, seriesOf]);
  const shareKey = shareSeries && seriesOrder.includes(shareSeries) ? shareSeries : seriesOrder[0];
  const shareRows = rows.filter((row) => seriesOf(row) === shareKey);

  const xOptions = [
    ...varying.filter((item) => item.name !== "seed").map((item) => ({ value: item.name, label: item.name })),
    { value: CASE_X, label: "each case" },
  ];
  const facetOptions = varying
    .filter((item) => item.name !== settings.x && item.name !== "seed" && item.values.length <= 6)
    .map((item) => ({ value: item.name, label: `${item.name} (${item.values.length})` }));

  return (
    <Stack gap="md">
      <Group gap="sm" align="flex-end" wrap="wrap">
        <Select label="X axis" data={xOptions} value={settings.x} onChange={(x) => x && setSettings({ ...settings, x, facet: settings.facet === x ? null : settings.facet })} allowDeselect={false} w={170} />
        <Select label="Split into panels by" placeholder="none" data={facetOptions} value={settings.facet} onChange={(facet) => setSettings({ ...settings, facet })} clearable w={200} />
        <Select label="Measure" data={METRICS.map((item) => ({ value: item.value, label: item.label }))} value={settings.metric} onChange={(metric) => metric && setSettings({ ...settings, metric: metric as Metric })} allowDeselect={false} w={160} />
        <Select
          label="Summary"
          data={[
            { value: "median", label: "Median" },
            { value: "mean", label: "Mean" },
            { value: "min", label: "Minimum" },
            { value: "max", label: "Maximum" },
          ]}
          value={settings.aggregate}
          onChange={(aggregate) => aggregate && setSettings({ ...settings, aggregate: aggregate as Aggregate })}
          allowDeselect={false}
          w={130}
        />
        <Switch label="Log scale" checked={settings.log} onChange={(event) => setSettings({ ...settings, log: event.currentTarget.checked })} mb={8} />
      </Group>
      {settings.x !== CASE_X && varying.filter((item) => item.name !== settings.x && item.name !== settings.facet && item.name !== "seed").length ? (
        <Text size="xs" c="dimmed">
          Each point summarises all runs that share the X value
          {settings.facet ? " and panel" : ""}; other parameters (
          {varying
            .filter((item) => item.name !== settings.x && item.name !== settings.facet && item.name !== "seed")
            .map((item) => item.name)
            .join(", ")}
          ) are pooled. Split into panels to separate them.
        </Text>
      ) : null}
      <FacetedCharts rows={rows} settings={settings} seriesOf={seriesOf} seriesOrder={seriesOrder} />

      <Paper withBorder p="md" radius="md">
        <Group justify="space-between" mb="xs">
          <Text fw={600} size="sm">
            Answers by {settings.x === CASE_X ? "case" : settings.x}
          </Text>
          <Select size="xs" data={seriesOrder} value={shareKey} onChange={setShareSeries} allowDeselect={false} w={220} aria-label="Solver for the answer chart" />
        </Group>
        <StatusShareChart rows={shareRows} x={settings.x} title="" />
        <StatusLegendNote />
      </Paper>

      <Paper withBorder p="md" radius="md">
        <Text fw={600} size="sm" mb="xs">
          Table view
        </Text>
        <AggregateTable rows={rows} settings={settings} seriesOf={seriesOf} />
      </Paper>
    </Stack>
  );
}

type SortKey = "index" | "case_label" | "solver_label" | "status" | "elapsed" | "decisions" | "conflicts" | "flips";

function sortValue(row: BenchmarkRow, key: SortKey): number | string {
  if (key === "decisions" || key === "conflicts" || key === "flips") {
    const value = row.stats[key];
    return typeof value === "number" ? value : -1;
  }
  return row[key] as number | string;
}

function RunsTable({
  rows,
  catalog,
  showRun,
  showProblem,
  onSelect,
}: {
  rows: BenchmarkRow[];
  catalog: Catalog;
  showRun: boolean;
  showProblem: boolean;
  onSelect: (row: BenchmarkRow) => void;
}) {
  const [statusFilter, setStatusFilter] = useState<string[]>([]);
  const [solverFilter, setSolverFilter] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [onlySuspicious, setOnlySuspicious] = useState(false);
  const [sort, setSort] = useState<{ key: SortKey; desc: boolean }>({ key: "index", desc: false });
  const suspicious = useMemo(() => new Set(suspiciousRows(rows)), [rows]);
  const solvers = useMemo(() => [...new Set(rows.map((row) => row.solver_label))], [rows]);
  const statuses = useMemo(() => [...new Set(rows.map((row) => row.status))], [rows]);

  const filtered = useMemo(() => {
    const text = query.toLowerCase();
    const list = rows.filter(
      (row) =>
        (!statusFilter.length || statusFilter.includes(row.status)) &&
        (!solverFilter.length || solverFilter.includes(row.solver_label)) &&
        (!onlySuspicious || suspicious.has(row)) &&
        (!text || row.case_label.toLowerCase().includes(text)),
    );
    return [...list].sort((a, b) => {
      const x = sortValue(a, sort.key);
      const y = sortValue(b, sort.key);
      const order = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y), undefined, { numeric: true });
      return sort.desc ? -order : order;
    });
  }, [rows, statusFilter, solverFilter, query, onlySuspicious, suspicious, sort]);

  const parent = useRef<HTMLDivElement | null>(null);
  const virtualizer = useVirtualizer({ count: filtered.length, getScrollElement: () => parent.current, estimateSize: () => 37, overscan: 12 });
  const problemTitle = (key: string) => catalog.problems.find((problem) => problem.key === key)?.title ?? key;

  const header = (key: SortKey, label: string, align: "left" | "right" = "left") => (
    <div role="columnheader" aria-sort={sort.key === key ? (sort.desc ? "descending" : "ascending") : "none"}>
      <UnstyledButton onClick={() => setSort({ key, desc: sort.key === key ? !sort.desc : key !== "index" && key !== "case_label" })} style={{ fontWeight: 600, fontSize: 13, textAlign: align, width: "100%" }}>
        <Group gap={2} justify={align === "right" ? "flex-end" : "flex-start"} wrap="nowrap">
          {label}
          {sort.key === key ? sort.desc ? <IconChevronDown size={12} /> : <IconChevronUp size={12} /> : null}
        </Group>
      </UnstyledButton>
    </div>
  );
  const plainHeader = (label: string) => (
    <div role="columnheader">
      <Text fw={600} size="sm">
        {label}
      </Text>
    </div>
  );

  const columns = `60px ${showRun ? "60px " : ""}${showProblem ? "130px " : ""}minmax(180px, 2fr) minmax(110px, 1fr) 90px 90px 90px 90px 80px`;

  return (
    <Stack gap="sm">
      <Group gap="sm" align="flex-end">
        <TextInput placeholder="Search cases" leftSection={<IconSearch size={14} />} value={query} onChange={(event) => setQuery(event.currentTarget.value)} w={220} aria-label="Search cases" />
        <MultiSelect placeholder="Status" data={statuses} value={statusFilter} onChange={setStatusFilter} clearable w={220} />
        <MultiSelect placeholder="Solver" data={solvers} value={solverFilter} onChange={setSolverFilter} clearable w={260} />
        <Switch label="Only suspicious" checked={onlySuspicious} onChange={(event) => setOnlySuspicious(event.currentTarget.checked)} mb={8} disabled={!suspicious.size} />
        <Text size="sm" c="dimmed" ml="auto">
          {formatCount(filtered.length)} runs
        </Text>
      </Group>
      {/* A virtualised list styled as a table; the ARIA roles give it table semantics. */}
      <Paper withBorder radius="md" style={{ overflow: "hidden" }} role="table" aria-label="Solver runs" aria-rowcount={filtered.length + 1}>
        <div role="row" aria-rowindex={1} style={{ display: "grid", gridTemplateColumns: columns, gap: 8, padding: "8px 12px", borderBottom: "1px solid var(--wz-hairline)" }} className="wz-num">
          {header("index", "#")}
          {showRun ? plainHeader("Run") : null}
          {showProblem ? plainHeader("Problem") : null}
          {header("case_label", "Case")}
          {header("solver_label", "Solver")}
          {header("status", "Answer")}
          {header("elapsed", "Time", "right")}
          {header("decisions", "Decisions", "right")}
          {header("conflicts", "Conflicts", "right")}
          {header("flips", "Flips", "right")}
        </div>
        <div ref={parent} style={{ height: 520, overflow: "auto" }}>
          <div role="rowgroup" style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
            {virtualizer.getVirtualItems().map((item) => {
              const row = filtered[item.index];
              const flag = suspicious.has(row);
              return (
                <div
                  key={item.key}
                  className="wz-table-row wz-num"
                  onClick={() => onSelect(row)}
                  role="row"
                  aria-rowindex={item.index + 2}
                  aria-label={`Run ${row.case_index + 1}: ${row.case_label}, ${row.solver_label}, ${row.status}. Press Enter for details.`}
                  tabIndex={0}
                  onKeyDown={(event) => event.key === "Enter" && onSelect(row)}
                  style={{
                    position: "absolute",
                    top: 0,
                    left: 0,
                    right: 0,
                    height: 37,
                    transform: `translateY(${item.start}px)`,
                    display: "grid",
                    gridTemplateColumns: columns,
                    gap: 8,
                    alignItems: "center",
                    padding: "0 12px",
                    borderBottom: "1px solid var(--wz-hairline)",
                    fontSize: 13,
                  }}
                >
                  <Cell>
                    {row.case_index + 1}
                    {row.repeat > 1 ? `.${row.repeat}` : ""}
                  </Cell>
                  {showRun ? <Cell>{row.run_label}</Cell> : null}
                  {showProblem ? (
                    <Cell>
                      <Text size="sm" truncate>
                        {problemTitle(row.problem)}
                      </Text>
                    </Cell>
                  ) : null}
                  <Cell>
                    <Text size="sm" truncate title={row.case_label}>
                      {row.case_label}
                    </Text>
                  </Cell>
                  <Cell>
                    <Text size="sm" truncate>
                      {row.solver_label}
                    </Text>
                  </Cell>
                  <Cell>
                    <Group gap={4} wrap="nowrap">
                      <RunStatusBadge status={row.status} size="xs" />
                      {flag ? <IconAlertTriangle size={14} color="var(--mantine-color-red-6)" aria-label="Suspicious answer" /> : null}
                    </Group>
                  </Cell>
                  <Cell right>{formatSeconds(row.elapsed)}</Cell>
                  <Cell right>{formatStat(row.stats.decisions)}</Cell>
                  <Cell right>{formatStat(row.stats.conflicts)}</Cell>
                  <Cell right>{formatStat(row.stats.flips)}</Cell>
                </div>
              );
            })}
          </div>
        </div>
      </Paper>
    </Stack>
  );
}

function Cell({ children, right = false }: { children: ReactNode; right?: boolean }) {
  return (
    <div role="cell" style={{ minWidth: 0, textAlign: right ? "right" : undefined }}>
      {children}
    </div>
  );
}

function RowDrawer({ row, jobId, request, catalog, onClose }: { row: BenchmarkRow | null; jobId: number; request: BenchmarkRequest; catalog: Catalog; onClose: () => void }) {
  const navigate = useNavigate();
  const own = row !== null && (row.run_label === undefined || row.run_label === `J${jobId}`);
  const sourceJob = row?.run_label ? Number(row.run_label.slice(1)) : jobId;
  const caseQuery = useQuery({
    queryKey: ["case", sourceJob, row?.index],
    queryFn: () => api.rowCase(sourceJob, row!.index),
    enabled: row !== null,
    staleTime: Infinity,
  });
  const problem = catalog.problems.find((item) => item.key === row?.problem);
  const solverSpec = catalog.solvers.find((item) => item.key === row?.solver);
  const entry = row && own ? entryForRow(request, row.index) : undefined;

  return (
    <Drawer opened={row !== null} onClose={onClose} position="right" size="xl" title={row ? <Text fw={650}>{row.case_label}</Text> : null}>
      {row && problem ? (
        <Stack gap="md">
          <Group gap="xs">
            <RunStatusBadge status={row.status} size="lg" />
            <Badge variant="default">{row.solver_label}</Badge>
            <Badge variant="default">{formatSeconds(row.elapsed)}</Badge>
            {row.verified ? (
              <Badge color="green" variant="light">
                verified
              </Badge>
            ) : null}
            {row.expected ? <Badge variant="outline">expected {row.expected}</Badge> : null}
          </Group>
          {row.error ? <Alert color="red">{row.error}</Alert> : null}
          {row.check_errors.length ? (
            <Alert color="red" title="Checks failed">
              {row.check_errors.map((error) => (
                <Text key={error} size="sm">
                  {error}
                </Text>
              ))}
            </Alert>
          ) : null}
          {row.rule ? (
            <Text size="sm" c="dimmed">
              Limit applied: {row.rule}
            </Text>
          ) : null}
          <FactsList
            facts={[
              { label: "Problem", value: problem.title },
              ...Object.entries(row.params)
                .filter(([name]) => name !== "problem" && name !== "run")
                .map(([name, value]) => ({ label: name, value: formatValue(value) })),
              { label: "Repeat", value: row.repeat },
              { label: "CNF variables", value: row.variables },
              { label: "CNF clauses", value: row.clauses },
              { label: "Time limit", value: row.timeout === null ? "none" : formatSeconds(row.timeout) },
            ]}
          />
          {Object.keys(row.stats).length ? <StatsTable stats={row.stats} /> : null}
          {solverSpec ? (
            <Paper withBorder p="md" radius="md">
              <Text fw={600} size="sm" mb="xs">
                Solver settings
              </Text>
              {entry && entry.solver === row.solver ? (
                <SolverSettingsTable spec={solverSpec} options={entry.options} />
              ) : (
                <Text size="sm" c="dimmed">
                  This run belongs to {row.run_label}; open that benchmark's Setup tab for its settings.
                </Text>
              )}
            </Paper>
          ) : null}
          <Group gap="xs">
            <Button
              leftSection={<IconWand size={16} />}
              variant="light"
              disabled={!caseQuery.data}
              onClick={() => navigate(`/solve/${row.problem}`, { state: { params: caseQuery.data?.params } })}
            >
              Open in Solve
            </Button>
            <Button component="a" href={urls.rowCnf(sourceJob, row.index)} variant="default" leftSection={<IconDownload size={16} />}>
              Download CNF
            </Button>
          </Group>
          <Paper withBorder p="md" radius="md">
            <Text fw={600} size="sm" mb="xs">
              {row.decoded ? "Answer" : "Input"}
            </Text>
            {caseQuery.isLoading ? (
              <Loader size="sm" />
            ) : caseQuery.data ? (
              <AnswerView view={problem.result_view} visual={caseQuery.data.instance.visual} decoded={row.decoded} />
            ) : (
              <Text size="sm" c="dimmed">
                Could not rebuild this case{own ? "" : " (it belongs to another run)"}.
              </Text>
            )}
          </Paper>
        </Stack>
      ) : null}
    </Drawer>
  );
}
