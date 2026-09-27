import { Badge, Button, Group, Loader, Paper, SimpleGrid, Stack, Text, TextInput, Tooltip } from "@mantine/core";
import { IconAlertTriangle, IconDownload, IconSearch } from "@tabler/icons-react";
import { useQuery } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import { useEffect, useMemo, useRef, useState } from "react";
import { api, urls } from "../api/client";
import { useLive } from "../api/live";
import type { Estimate, Fact, LogLine } from "../api/types";
import { formatCount } from "../lib/format";

export function FactsList({ facts }: { facts: Fact[] }) {
  return (
    <SimpleGrid cols={{ base: 2, sm: 3 }} spacing="xs" verticalSpacing="xs">
      {facts.map((fact) => (
        <div key={`${fact.label}-${fact.value}`}>
          <Text size="xs" c="dimmed">
            {fact.label}
          </Text>
          <Tooltip label={fact.hint} disabled={!fact.hint}>
            <Text size="sm" fw={600} className="wz-num" style={{ wordBreak: "break-word" }}>
              {typeof fact.value === "number" ? formatCount(fact.value) : fact.value}
              {fact.hint ? <IconAlertTriangle size={12} style={{ marginLeft: 4 }} /> : null}
            </Text>
          </Tooltip>
        </div>
      ))}
    </SimpleGrid>
  );
}

export function StatTile({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  return (
    <Paper withBorder p="sm" radius="md">
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text fw={650} size="lg" mt={2}>
        {value}
      </Text>
      {hint ? (
        <Text size="xs" c="dimmed">
          {hint}
        </Text>
      ) : null}
    </Paper>
  );
}

export function EstimateBadge({ estimate, tooLarge, maxClauses }: { estimate: Estimate | null | undefined; tooLarge?: boolean; maxClauses?: number }) {
  if (!estimate) return null;
  return (
    <Tooltip
      label={
        tooLarge
          ? `Above the ${formatCount(maxClauses ?? 0)} clause limit: choose smaller parameters.`
          : "Size of the CNF formula, computed from the parameters before encoding."
      }
    >
      <Badge color={tooLarge ? "red" : "gray"} variant="light" size="lg" radius="sm" className="wz-num">
        ~{formatCount(estimate.variables, "compact")} vars · {formatCount(estimate.clauses, "compact")} clauses
      </Badge>
    </Tooltip>
  );
}

const ROW_HEIGHT = 20;

function VirtualLines({
  count,
  height,
  render,
  follow,
}: {
  count: number;
  height: number;
  render: (index: number) => React.ReactNode;
  follow?: boolean;
}) {
  const parent = useRef<HTMLDivElement | null>(null);
  const virtualizer = useVirtualizer({ count, getScrollElement: () => parent.current, estimateSize: () => ROW_HEIGHT, overscan: 20 });
  const stick = useRef(true);
  useEffect(() => {
    if (follow && stick.current && count > 0) virtualizer.scrollToIndex(count - 1, { align: "end" });
  }, [count, follow, virtualizer]);
  return (
    <div
      ref={parent}
      className="wz-lines"
      style={{ height, overflow: "auto" }}
      onScroll={(event) => {
        const element = event.currentTarget;
        stick.current = element.scrollHeight - element.scrollTop - element.clientHeight < 40;
      }}
    >
      <div style={{ height: virtualizer.getTotalSize(), position: "relative" }}>
        {virtualizer.getVirtualItems().map((item) => (
          <div key={item.key} className="wz-line" style={{ position: "absolute", top: 0, left: 0, right: 0, height: ROW_HEIGHT, transform: `translateY(${item.start}px)` }}>
            {render(item.index)}
          </div>
        ))}
      </div>
    </div>
  );
}

/** Live log of a job: streamed lines, with a search box and a "full log" loader. */
export function LogViewer({ jobId, height = 280, initial }: { jobId: number; height?: number; initial?: LogLine[] }) {
  const live = useLive((state) => state.logs[jobId]);
  const [full, setFull] = useState<LogLine[] | null>(null);
  const [query, setQuery] = useState("");
  const lines = full ?? live ?? initial ?? [];
  const filtered = useMemo(
    () => (query ? lines.filter(([, message]) => message.toLowerCase().includes(query.toLowerCase())) : lines),
    [lines, query],
  );
  return (
    <Stack gap={6}>
      <Group gap="xs">
        <TextInput
          size="xs"
          placeholder="Filter log"
          leftSection={<IconSearch size={14} />}
          value={query}
          onChange={(event) => setQuery(event.currentTarget.value)}
          style={{ flex: 1 }}
          aria-label="Filter log"
        />
        <Button size="compact-sm" variant="default" onClick={() => api.logs(jobId).then(setFull)}>
          Load full log
        </Button>
      </Group>
      <VirtualLines
        count={filtered.length}
        height={height}
        follow={!query}
        render={(index) => (
          <>
            <span className="wz-line-number">{filtered[index][0]}</span>
            {filtered[index][1]}
          </>
        )}
      />
    </Stack>
  );
}

const PAGE = 500;

/** Paged, virtualized DIMACS viewer for a job's instance.cnf. */
export function CnfViewer({ jobId, height = 360 }: { jobId: number; height?: number }) {
  const [pages, setPages] = useState<Record<number, string[]>>({});
  const first = useQuery({ queryKey: ["cnf", jobId, 0], queryFn: () => api.cnf(jobId, 0, PAGE) });
  const total = first.data?.total ?? 0;
  const loading = useRef(new Set<number>());

  useEffect(() => {
    if (first.data) setPages((current) => ({ ...current, 0: first.data.lines }));
  }, [first.data]);

  const lineAt = (index: number): string | null => {
    const page = Math.floor(index / PAGE);
    const lines = pages[page];
    if (!lines) {
      if (!loading.current.has(page)) {
        loading.current.add(page);
        void api.cnf(jobId, page * PAGE, PAGE).then((data) => setPages((current) => ({ ...current, [page]: data.lines })));
      }
      return null;
    }
    return lines[index - page * PAGE] ?? "";
  };

  if (first.isLoading) return <Loader size="sm" />;
  if (first.isError) {
    return (
      <Text size="sm" c="dimmed">
        No CNF file for this job.
      </Text>
    );
  }
  return (
    <Stack gap={6}>
      <Group justify="space-between">
        <Text size="xs" c="dimmed">
          {formatCount(total)} lines. Variable numbers are readable: see the problem description.
        </Text>
        <Button component="a" href={urls.file(jobId, "instance.cnf")} size="compact-sm" variant="light" leftSection={<IconDownload size={14} />}>
          Download .cnf
        </Button>
      </Group>
      <VirtualLines
        count={total}
        height={height}
        render={(index) => {
          const line = lineAt(index);
          return (
            <>
              <span className="wz-line-number">{index + 1}</span>
              <span style={{ color: line?.startsWith("c") ? "var(--wz-muted)" : undefined }}>{line ?? "..."}</span>
            </>
          );
        }}
      />
    </Stack>
  );
}
