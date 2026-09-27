import { Group, Paper, SimpleGrid, Table, Text } from "@mantine/core";
import { useCallback, useMemo } from "react";
import type { BenchmarkRow } from "../../api/types";
import { formatCount, formatSeconds } from "../../lib/format";
import { formatValue } from "../../lib/params";
import { CATEGORICAL, RUN_STATUS_ORDER, runStatusColor, type Scheme } from "../../lib/palette";
import { seriesByX, statusShares, type Aggregate, type Metric, METRICS } from "../../lib/stats";
import { baseOption, EChart, escapeHtml } from "./EChart";

export interface ChartSettings {
  x: string; // parameter name, or "__case" for one bar group per case
  facet: string | null;
  metric: Metric;
  aggregate: Aggregate;
  log: boolean;
}

const CASE_X = "__case";
const AGGREGATE_LABELS: Record<Aggregate, string> = { median: "Median", mean: "Mean", min: "Minimum", max: "Maximum" };

function xAccessor(x: string) {
  return (row: BenchmarkRow) => (x === CASE_X ? row.case_label : row.params[x]);
}

function metricText(metric: Metric, value: number | null): string {
  if (value === null) return "-";
  return metric === "elapsed" ? formatSeconds(value) : formatCount(Math.round(value));
}

/** Solver series keep one colour per entity (in first-seen order), whatever the filter. */
export function useSeriesColors(keys: string[]): Map<string, number> {
  return useMemo(() => new Map(keys.map((key, index) => [key, index])), [keys]);
}

export function MetricChart({
  rows,
  settings,
  seriesOf,
  seriesOrder,
  title,
  height = 300,
}: {
  rows: BenchmarkRow[];
  settings: ChartSettings;
  seriesOf: (row: BenchmarkRow) => string;
  seriesOrder: string[];
  title: string;
  height?: number;
}) {
  const metric = METRICS.find((item) => item.value === settings.metric)!;
  const data = useMemo(() => seriesByX(rows, xAccessor(settings.x), seriesOf, settings.metric, settings.aggregate), [rows, settings, seriesOf]);
  const numericX = settings.x !== CASE_X && data.xs.every((x) => typeof x === "number");
  const asLine = numericX && data.xs.length > 1;

  const option = useCallback(
    (scheme: Scheme) => {
      const base = baseOption(scheme);
      const { axisCommon: _axis, tooltipCommon: _tooltip, legendCommon: _legend, chrome: _chrome, ...root } = base;
      const series = data.series.map((key) => {
        const colorIndex = seriesOrder.indexOf(key);
        const color = CATEGORICAL[scheme][colorIndex] ?? base.chrome.muted;
        const points = data.points.get(key) ?? [];
        const values = points.map((point) => (point.value === null || (settings.log && point.value <= 0) ? null : point.value));
        return asLine
          ? {
              name: key,
              type: "line" as const,
              data: points.map((point, index) => [point.x, values[index]]),
              lineStyle: { width: 2, color },
              itemStyle: { color, borderColor: base.chrome.surface, borderWidth: 2 },
              symbol: "circle",
              symbolSize: 8,
              connectNulls: false,
              emphasis: { focus: "series" as const },
            }
          : {
              name: key,
              type: "bar" as const,
              data: values,
              barMaxWidth: 24,
              barGap: "12%",
              itemStyle: { color, borderRadius: [4, 4, 0, 0], borderColor: base.chrome.surface, borderWidth: 1 },
            };
      });
      const valueAxis = {
        type: settings.log ? ("log" as const) : ("value" as const),
        ...base.axisCommon,
        axisLabel: {
          ...base.axisCommon.axisLabel,
          formatter: (value: number) => (settings.metric === "elapsed" ? formatSeconds(value) : formatCount(value, "compact")),
        },
      };
      const categoryAxis = asLine
        ? { type: "value" as const, name: settings.x, nameLocation: "middle" as const, nameGap: 26, min: "dataMin", max: "dataMax", ...base.axisCommon, splitLine: { show: false } }
        : {
            type: "category" as const,
            data: data.xs.map((x) => formatValue(x)),
            ...base.axisCommon,
            splitLine: { show: false },
            axisLabel: { ...base.axisCommon.axisLabel, rotate: data.xs.length > 8 ? 35 : 0, hideOverlap: true },
          };
      return {
        ...root,
        title: { text: title, left: 0, top: 0, textStyle: { fontSize: 13, fontWeight: 600, color: base.chrome.text } },
        legend: { ...base.legendCommon, show: data.series.length > 1, top: 22, icon: asLine ? "path://M0,4 L14,4" : "roundRect" },
        grid: { ...base.grid, top: data.series.length > 1 ? 56 : 36, bottom: asLine ? 24 : 8 },
        tooltip: {
          ...base.tooltipCommon,
          trigger: "axis",
          axisPointer: { type: asLine ? "line" : "shadow", lineStyle: { color: base.chrome.axis } },
          formatter: (params: { seriesName: string; value: unknown; color: string; axisValueLabel?: string; dataIndex: number }[]) => {
            const list = Array.isArray(params) ? params : [params];
            const header = asLine ? `${escapeHtml(settings.x)} = ${escapeHtml(formatValue(data.xs[list[0]?.dataIndex ?? 0]))}` : escapeHtml(list[0]?.axisValueLabel ?? "");
            const lines = list.map((item) => {
              const point = data.points.get(item.seriesName)?.[item.dataIndex];
              const value = point?.value ?? null;
              return `<div style="display:flex;gap:8px;align-items:center;justify-content:space-between"><span style="display:flex;align-items:center;gap:6px"><span style="display:inline-block;width:12px;height:2px;background:${item.color}"></span>${escapeHtml(item.seriesName)}</span><b>${escapeHtml(metricText(settings.metric, value))}</b><span style="opacity:.6">n=${point?.count ?? 0}</span></div>`;
            });
            return `<div style="margin-bottom:4px;font-weight:600">${header}</div>${lines.join("")}`;
          },
        },
        xAxis: asLine ? categoryAxis : categoryAxis,
        yAxis: valueAxis,
        series,
      };
    },
    [data, settings, asLine, seriesOrder, metric, title],
  );

  return <EChart option={option} height={height} ariaLabel={`${title}: ${metric.label} by ${settings.x}`} />;
}

export function StatusShareChart({ rows, x, title, height = 240 }: { rows: BenchmarkRow[]; x: string; title: string; height?: number }) {
  const shares = useMemo(() => statusShares(rows, xAccessor(x)), [rows, x]);
  const statuses = RUN_STATUS_ORDER.filter((status) => shares.some((share) => share.counts[status]));

  const option = useCallback(
    (scheme: Scheme) => {
      const base = baseOption(scheme);
      const { axisCommon: _axis, tooltipCommon: _tooltip, legendCommon: _legend, chrome: _chrome, ...root } = base;
      return {
        ...root,
        title: { text: title, left: 0, top: 0, textStyle: { fontSize: 13, fontWeight: 600, color: base.chrome.text } },
        legend: { ...base.legendCommon, top: 22 },
        grid: { ...base.grid, top: 56 },
        tooltip: {
          ...base.tooltipCommon,
          trigger: "axis",
          axisPointer: { type: "shadow" },
          formatter: (params: { dataIndex: number }[]) => {
            const share = shares[params[0]?.dataIndex ?? 0];
            const lines = statuses
              .filter((status) => share.counts[status])
              .map(
                (status) =>
                  `<div style="display:flex;gap:10px;justify-content:space-between"><span><span style="display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;background:${runStatusColor(status, scheme)}"></span>${status}</span><b>${Math.round((share.counts[status] / share.total) * 100)}%</b><span style="opacity:.6">${share.counts[status]}/${share.total}</span></div>`,
              );
            return `<div style="margin-bottom:4px;font-weight:600">${escapeHtml(x === CASE_X ? "case" : x)} = ${escapeHtml(formatValue(share.x))}</div>${lines.join("")}`;
          },
        },
        xAxis: {
          type: "category",
          data: shares.map((share) => formatValue(share.x)),
          ...base.axisCommon,
          splitLine: { show: false },
          axisLabel: { ...base.axisCommon.axisLabel, rotate: shares.length > 8 ? 35 : 0, hideOverlap: true },
        },
        yAxis: { type: "value", max: 100, ...base.axisCommon, axisLabel: { ...base.axisCommon.axisLabel, formatter: "{value}%" } },
        series: statuses.map((status, index) => ({
          name: status,
          type: "bar",
          stack: "status",
          barMaxWidth: 24,
          data: shares.map((share) => (share.total ? ((share.counts[status] ?? 0) / share.total) * 100 : 0)),
          itemStyle: {
            color: runStatusColor(status, scheme),
            borderColor: base.chrome.surface,
            borderWidth: 1,
            borderRadius: index === statuses.length - 1 ? [4, 4, 0, 0] : 0,
          },
        })),
      };
    },
    [shares, statuses, title, x],
  );

  return <EChart option={option} height={height} ariaLabel={`${title}: status share by ${x}`} />;
}

/** Table twin of the metric chart (every value readable without hovering). */
export function AggregateTable({
  rows,
  settings,
  seriesOf,
}: {
  rows: BenchmarkRow[];
  settings: ChartSettings;
  seriesOf: (row: BenchmarkRow) => string;
}) {
  const data = useMemo(() => seriesByX(rows, xAccessor(settings.x), seriesOf, settings.metric, settings.aggregate), [rows, settings, seriesOf]);
  return (
    <Table.ScrollContainer minWidth={400} maxHeight={320}>
      <Table striped stickyHeader className="wz-num" fz="sm">
        <Table.Thead>
          <Table.Tr>
            <Table.Th>{settings.x === CASE_X ? "Case" : settings.x}</Table.Th>
            {data.series.map((key) => (
              <Table.Th key={key} ta="right">
                {key}
              </Table.Th>
            ))}
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {data.xs.map((x, index) => (
            <Table.Tr key={JSON.stringify(x)}>
              <Table.Td>{formatValue(x)}</Table.Td>
              {data.series.map((key) => {
                const point = data.points.get(key)?.[index];
                return (
                  <Table.Td key={key} ta="right">
                    {metricText(settings.metric, point?.value ?? null)}
                    <Text span size="xs" c="dimmed">
                      {" "}
                      (n={point?.count ?? 0})
                    </Text>
                  </Table.Td>
                );
              })}
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}

/** Small multiples: one metric chart per facet value, sharing the settings. */
export function FacetedCharts({
  rows,
  settings,
  seriesOf,
  seriesOrder,
}: {
  rows: BenchmarkRow[];
  settings: ChartSettings;
  seriesOf: (row: BenchmarkRow) => string;
  seriesOrder: string[];
}) {
  const metricLabel = METRICS.find((item) => item.value === settings.metric)!.label;
  const groups = useMemo(() => {
    if (!settings.facet) return [{ key: "all", label: "", rows }];
    const map = new Map<string, BenchmarkRow[]>();
    for (const row of rows) {
      const key = formatValue(row.params[settings.facet]);
      map.set(key, [...(map.get(key) ?? []), row]);
    }
    return [...map.entries()]
      .sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }))
      .map(([key, group]) => ({ key, label: `${settings.facet} = ${key}`, rows: group }));
  }, [rows, settings.facet]);

  if (groups.length > 6) {
    return (
      <Text size="sm" c="dimmed">
        Splitting by {settings.facet} gives {groups.length} panels; choose a parameter with at most 6 values.
      </Text>
    );
  }

  return (
    <SimpleGrid cols={{ base: 1, lg: groups.length > 1 ? 2 : 1 }} spacing="md">
      {groups.map((group) => (
        <Paper key={group.key} withBorder p="md" radius="md">
          <MetricChart
            rows={group.rows}
            settings={settings}
            seriesOf={seriesOf}
            seriesOrder={seriesOrder}
            title={`${AGGREGATE_LABELS[settings.aggregate]} ${metricLabel.toLowerCase()}${settings.log ? " (log scale)" : ""}${group.label ? ` - ${group.label}` : ""}`}
          />
        </Paper>
      ))}
    </SimpleGrid>
  );
}

export function StatusLegendNote() {
  return (
    <Group gap="xs">
      <Text size="xs" c="dimmed">
        SAT and UNSAT are both answers; UNKNOWN means an incomplete solver gave up, TIMEOUT that the time limit was hit.
      </Text>
    </Group>
  );
}

export { CASE_X };
