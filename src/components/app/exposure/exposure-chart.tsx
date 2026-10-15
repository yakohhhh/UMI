"use client";

import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatDuration } from "@/lib/format";
import type { ExposurePeriod } from "@/lib/types";

export interface Threshold {
  y: number;
  label: string;
  color: string;
}

function TooltipCard({ active, payload, unit, digits }: { active?: boolean; payload?: { payload: ExposurePeriod; value: number }[]; unit: string; digits: number }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-xl border border-line bg-surface px-3 py-2 text-xs shadow-[var(--shadow-lift)]">
      <p className="font-medium text-fg">{p.label}</p>
      {payload[0].value === null || payload[0].value === undefined ? (
        <p className="text-fg-muted">No rides</p>
      ) : (
        <p className="text-fg-muted">
          <span className="font-num text-sm font-semibold text-fg">{Number(payload[0].value).toFixed(digits)}</span> {unit} · {formatDuration(p.rideMin * 60)} riding
        </p>
      )}
    </div>
  );
}

/**
 * Ride-weighted exposure per week or month. Bars are coloured by threshold
 * class; the thresholds are drawn as dashed lines and listed in the legend.
 */
export function ExposureChart({
  data,
  dataKey,
  unit,
  thresholds,
  colorFor,
  domain,
  digits = 1,
  label,
  ticks,
}: {
  data: ExposurePeriod[];
  dataKey: "pm25" | "db";
  unit: string;
  thresholds: Threshold[];
  colorFor: (v: number) => string;
  domain: [number | "auto" | "dataMin" | "dataMax", number | "auto" | "dataMin" | "dataMax"];
  digits?: number;
  label: string;
  ticks?: number[];
}) {
  const values = data.map((d) => d[dataKey]).filter((v): v is number => v !== null);
  const max = Math.max(...values);
  const min = Math.min(...values);
  const lastFull = [...data].reverse().find((d) => d[dataKey] !== null);
  return (
    <figure aria-label={`${label}: from ${min.toFixed(digits)} to ${max.toFixed(digits)} ${unit}${lastFull ? `, latest ${lastFull[dataKey]?.toFixed(digits)} ${unit} (${lastFull.label})` : ""}.`}>
      <div className="h-60" aria-hidden>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 4, bottom: 0, left: -14 }} barCategoryGap="22%">
            <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
            <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--fg-subtle)" }} interval="preserveStartEnd" minTickGap={10} />
            <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--fg-subtle)", fontFamily: "var(--font-mono)" }} width={44} domain={domain} ticks={ticks} allowDataOverflow />
            <Tooltip cursor={{ fill: "var(--surface-2)", opacity: 0.7 }} content={<TooltipCard unit={unit} digits={digits} />} isAnimationActive={false} />
            <Bar dataKey={dataKey} radius={[5, 5, 1, 1]} maxBarSize={30} isAnimationActive={false}>
              {data.map((d, i) => (
                <Cell key={i} fill={d[dataKey] === null ? "transparent" : colorFor(d[dataKey] as number)} fillOpacity={0.9} />
              ))}
            </Bar>
            {thresholds.map((t) => (
              <ReferenceLine key={t.label} y={t.y} stroke={t.color} strokeDasharray="5 4" strokeWidth={1.4} ifOverflow="extendDomain" />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-fg-muted" aria-label="Reference lines">
        {thresholds.map((t) => (
          <li key={t.label} className="inline-flex items-center gap-1.5">
            <svg width="18" height="4" aria-hidden>
              <line x1="0" y1="2" x2="18" y2="2" stroke={t.color} strokeWidth="2" strokeDasharray="4 3" />
            </svg>
            {t.label}{" "}
            <span className="font-num text-fg-subtle">
              {t.y} {unit}
            </span>
          </li>
        ))}
      </ul>
    </figure>
  );
}
