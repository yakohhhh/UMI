"use client";

import { useId } from "react";
import { Area, AreaChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { cn } from "@/lib/utils";

export interface TimelinePoint {
  t: number; // minutes since start
  [key: string]: number;
}

export interface TimelineSeries {
  key: string;
  label: string;
  unit: string;
  color: string;
  digits?: number;
  domain?: [number | "auto", number | "auto"];
  /** Dashed thresholds; labels sit above the line unless `below` is set. */
  references?: { y: number; label: string; color?: string; below?: boolean }[];
  events?: { t: number; label: string }[];
}

/**
 * One metric over time. Several of these share `syncId` so hovering any of them
 * moves the same cursor everywhere (and, via onHover, the dot on the map).
 */
export function TimelineChart({
  data,
  series,
  syncId,
  activeIndex,
  onHover,
  showAxis = false,
  height = 112,
  className,
}: {
  data: TimelinePoint[];
  series: TimelineSeries;
  syncId: string;
  activeIndex: number | null;
  onHover: (index: number | null) => void;
  showAxis?: boolean;
  height?: number;
  className?: string;
}) {
  const gid = useId().replace(/:/g, "");
  const current = activeIndex !== null ? data[activeIndex] : null;
  const values = data.map((d) => d[series.key]);
  const avg = values.reduce((a, b) => a + b, 0) / values.length;
  const max = Math.max(...values);
  const digits = series.digits ?? 0;

  return (
    <figure className={cn("relative", className)} aria-label={`${series.label} over the ride: average ${avg.toFixed(digits)} ${series.unit}, maximum ${max.toFixed(digits)} ${series.unit}`}>
      <figcaption className="flex items-baseline justify-between px-1">
        <span className="flex items-center gap-2 text-xs font-medium text-fg-muted">
          <span className="size-2 rounded-full" style={{ background: series.color }} aria-hidden />
          {series.label}
        </span>
        <span className="font-mono text-xs text-fg">
          {current ? (
            <>
              <span className="font-num text-sm font-semibold">{current[series.key].toFixed(digits)}</span> {series.unit}
            </>
          ) : (
            <span className="text-fg-muted">
              avg <span className="font-num font-semibold text-fg">{avg.toFixed(digits)}</span> · max <span className="font-num font-semibold text-fg">{max.toFixed(digits)}</span> {series.unit}
            </span>
          )}
        </span>
      </figcaption>
      <div style={{ height }} aria-hidden>
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart
            data={data}
            syncId={syncId}
            margin={{ top: 6, right: 4, bottom: 0, left: 4 }}
            onMouseMove={(state) => {
              const i = state?.activeTooltipIndex;
              if (i === undefined || i === null) return;
              const n = Number(i);
              if (Number.isFinite(n) && n !== activeIndex) onHover(n);
            }}
            onMouseLeave={() => onHover(null)}
          >
            <defs>
              <linearGradient id={`tl-${gid}`} x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor={series.color} stopOpacity={0.32} />
                <stop offset="100%" stopColor={series.color} stopOpacity={0.02} />
              </linearGradient>
            </defs>
            <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
            <XAxis
              dataKey="t"
              type="number"
              domain={["dataMin", "dataMax"]}
              tickFormatter={(v: number) => `${Math.round(v)}′`}
              hide={!showAxis}
              tick={{ fontSize: 11, fill: "var(--fg-subtle)", fontFamily: "var(--font-mono)" }}
              tickLine={false}
              axisLine={false}
              tickCount={8}
            />
            <YAxis hide domain={series.domain ?? ["auto", "auto"]} />
            <Tooltip content={() => null} cursor={{ stroke: "var(--fg)", strokeOpacity: 0.5, strokeWidth: 1 }} isAnimationActive={false} />
            {series.references?.map((r) => (
              <ReferenceLine
                key={r.label}
                y={r.y}
                stroke={r.color ?? "var(--fg-subtle)"}
                strokeDasharray="4 4"
                label={{ value: r.label, position: r.below ? "insideTopRight" : "insideBottomRight", fill: r.color ?? "var(--fg-subtle)", fontSize: 10, fontFamily: "var(--font-mono)" }}
              />
            ))}
            {series.events?.map((e) => (
              <ReferenceLine key={`${e.t}-${e.label}`} x={e.t} stroke="var(--color-signal)" strokeDasharray="2 3" label={{ value: e.label, position: "insideTopLeft", fill: "var(--accent-ink)", fontSize: 10 }} />
            ))}
            <Area
              type="monotone"
              dataKey={series.key}
              stroke={series.color}
              strokeWidth={1.8}
              fill={`url(#tl-${gid})`}
              isAnimationActive={false}
              activeDot={{ r: 4, fill: series.color, stroke: "var(--surface)", strokeWidth: 2 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </figure>
  );
}
