import { Select } from "@mantine/core";
import { useMemo } from "react";
import { useStatSpecs } from "../../api/queries";
import { chartMetrics, type Metric } from "../../lib/stats";

/** Picks what the benchmark charts show: time or one of the statistics the catalog marks for charts. */
export function MeasureSelect({ value, onChange }: { value: Metric; onChange: (metric: Metric) => void }) {
  const stats = useStatSpecs();
  const data = useMemo(() => chartMetrics(stats), [stats]);
  return <Select label="Measure" data={data} value={value} onChange={(metric) => metric && onChange(metric)} allowDeselect={false} w={160} />;
}
