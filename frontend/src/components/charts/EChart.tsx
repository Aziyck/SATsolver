import { useComputedColorScheme } from "@mantine/core";
import * as echarts from "echarts/core";
import { BarChart, LineChart } from "echarts/charts";
import { AxisPointerComponent, GridComponent, LegendComponent, TitleComponent, ToolboxComponent, TooltipComponent } from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import type { EChartsCoreOption } from "echarts/core";
import { useEffect, useRef } from "react";
import { CHROME, type Scheme } from "../../lib/palette";

echarts.use([LineChart, BarChart, GridComponent, TooltipComponent, LegendComponent, TitleComponent, ToolboxComponent, AxisPointerComponent, CanvasRenderer]);

/** Thin ECharts wrapper: owns the instance, resizes with its container, re-renders on option changes. */
export function EChart({ option, height, ariaLabel }: { option: (scheme: Scheme) => EChartsCoreOption; height: number; ariaLabel: string }) {
    const container = useRef<HTMLDivElement | null>(null);
    const chart = useRef<echarts.ECharts | null>(null);
    const scheme = useComputedColorScheme("light") as Scheme;

    useEffect(() => {
      if (!container.current) return;
      const instance = echarts.init(container.current, undefined, { renderer: "canvas" });
      chart.current = instance;
      const observer = new ResizeObserver(() => instance.resize());
      observer.observe(container.current);
      return () => {
        observer.disconnect();
        instance.dispose();
        chart.current = null;
      };
    }, []);

    useEffect(() => {
      const chrome = CHROME[scheme];
      chart.current?.setOption(
        {
          ...option(scheme),
          toolbox: {
            right: 0,
            top: 0,
            itemSize: 14,
            iconStyle: { borderColor: chrome.muted },
            feature: { saveAsImage: { title: "Save as PNG", pixelRatio: 2, backgroundColor: chrome.surface, name: "wizsat-chart" } },
          },
        },
        { notMerge: true },
      );
    }, [option, scheme]);

    return <div ref={container} className="wz-chart" style={{ height }} role="img" aria-label={ariaLabel} />;
}

/** Shared axis/grid styling: hairline, recessive, one axis only. */
export function baseOption(scheme: Scheme) {
  const chrome = CHROME[scheme];
  const axisLabel = { color: chrome.muted, fontSize: 11 };
  return {
    backgroundColor: "transparent",
    textStyle: { fontFamily: 'system-ui, -apple-system, "Segoe UI", sans-serif', color: chrome.secondary },
    grid: { left: 8, right: 16, top: 36, bottom: 8, containLabel: true },
    axisCommon: {
      axisLine: { lineStyle: { color: chrome.axis, width: 1 } },
      axisTick: { show: false },
      splitLine: { lineStyle: { color: chrome.grid, width: 1, type: "solid" as const } },
      axisLabel,
      nameTextStyle: { color: chrome.muted, fontSize: 11 },
    },
    tooltipCommon: {
      backgroundColor: chrome.surface,
      borderColor: scheme === "light" ? "rgba(11,11,11,0.10)" : "rgba(255,255,255,0.10)",
      textStyle: { color: chrome.text, fontSize: 12 },
      extraCssText: "box-shadow: 0 4px 16px rgba(0,0,0,0.12); border-radius: 8px;",
    },
    legendCommon: {
      top: 0,
      left: 0,
      itemWidth: 14,
      itemHeight: 8,
      textStyle: { color: chrome.secondary, fontSize: 12 },
      icon: "roundRect",
    },
    chrome,
  };
}

export function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char] as string);
}
