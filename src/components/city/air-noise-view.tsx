"use client";

import { useMemo, useRef, useState } from "react";
import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Segmented } from "@/components/ui/segmented";
import { Skeleton } from "@/components/ui/skeleton";
import { getAirNoise } from "@/lib/api";
import { formatInt, hourLabel } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";
import { BAND_VAR, type ScoreBand } from "@/lib/score";
import type { AirNoiseCell } from "@/lib/types";
import { cn } from "@/lib/utils";
import { PERIOD_LABEL, useCityFilters } from "./city-filters";
import { PageHeader } from "./page-header";

type Metric = "pm25" | "db";
const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const LOW_CONFIDENCE = 40;

const META: Record<Metric, { label: string; unit: string; digits: number; band: (v: number) => ScoreBand; thresholds: { y: number; label: string; color: string }[]; legend: Record<ScoreBand, string> }> = {
  pm25: {
    label: "PM2.5",
    unit: "µg/m³",
    digits: 1,
    band: (v) => (v <= 10 ? "good" : v <= 15 ? "mid" : "bad"),
    thresholds: [
      { y: 10, label: "EU 2030 limit · 10", color: "var(--fg-muted)" },
      { y: 15, label: "WHO 24 h · 15", color: "var(--bad-fill)" },
    ],
    legend: { good: "≤ 10 · under the EU 2030 limit", mid: "10–15", bad: "> 15 · above the WHO 24 h guideline" },
  },
  db: {
    label: "Noise",
    unit: "dB(A)",
    digits: 0,
    band: (v) => (v <= 58 ? "good" : v <= 64 ? "mid" : "bad"),
    thresholds: [
      { y: 53, label: "WHO road traffic · 53", color: "var(--good-fill)" },
      { y: 65, label: "High exposure · 65", color: "var(--bad-fill)" },
    ],
    legend: { good: "≤ 58 dB(A)", mid: "58–64", bad: "> 64 dB(A)" },
  },
};

function Heatmap({ grid, metric }: { grid: AirNoiseCell[][]; metric: Metric }) {
  const meta = META[metric];
  const [hover, setHover] = useState<{ d: number; h: number; x: number; y: number } | null>(null);
  const wrapRef = useRef<HTMLDivElement>(null);
  const values = grid.flat().map((c) => c[metric]);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const cell = hover ? grid[hover.d][hover.h] : null;

  return (
    <div ref={wrapRef} className="relative">
      <div className="scrollbar-none relative overflow-x-auto pb-1" onScroll={() => setHover(null)}>
        <table className="w-full min-w-[760px] table-fixed border-separate border-spacing-[3px] text-[10px]" onMouseLeave={() => setHover(null)}>
          <caption className="sr-only">
            {meta.label} by weekday and hour, {meta.unit}. Values range from {min.toFixed(meta.digits)} to {max.toFixed(meta.digits)}.
          </caption>
          <thead>
            <tr>
              <th scope="col" className="w-10">
                <span className="sr-only">Day</span>
              </th>
              {Array.from({ length: 24 }, (_, h) => (
                <th key={h} scope="col" className="font-mono font-normal text-fg-subtle">
                  {h % 3 === 0 ? String(h).padStart(2, "0") : <span className="sr-only">{hourLabel(h)}</span>}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {grid.map((row, d) => (
              <tr key={d}>
                <th scope="row" className="pr-1 text-left font-mono font-normal text-fg-subtle">
                  <abbr title={DAYS[d]} className="no-underline">
                    {DAYS[d].slice(0, 3)}
                  </abbr>
                </th>
                {row.map((c, h) => {
                  const v = c[metric];
                  const b = meta.band(v);
                  const t = max > min ? (v - min) / (max - min) : 0.5;
                  const low = c.rides < LOW_CONFIDENCE;
                  return (
                    <td
                      key={h}
                      onMouseEnter={(e) => {
                        const r = e.currentTarget.getBoundingClientRect();
                        const w = wrapRef.current?.getBoundingClientRect();
                        setHover({ d, h, x: r.left + r.width / 2 - (w?.left ?? 0), y: r.top - (w?.top ?? 0) });
                      }}
                      className={cn("h-9 rounded-[5px] text-center font-num font-medium transition-[outline] sm:h-10", hover?.d === d && hover?.h === h && "outline-2 outline-fg")}
                      style={{
                        background: `color-mix(in srgb, ${BAND_VAR[b].fill} ${Math.round(46 + t * 50)}%, var(--surface-2))`,
                        color: t > 0.55 ? "#0b1220" : "var(--fg)",
                        backgroundImage: low ? "repeating-linear-gradient(135deg, transparent 0 4px, rgb(127 127 127 / 0.18) 4px 5px)" : undefined,
                      }}
                    >
                      <span className="hidden lg:inline">{v.toFixed(metric === "pm25" ? 0 : 0)}</span>
                      <span className="sr-only lg:hidden">
                        {v.toFixed(meta.digits)} {meta.unit}
                      </span>
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {hover && cell ? (
        <div
          className="pointer-events-none absolute z-10 rounded-lg border border-line bg-surface px-3 py-2 text-xs whitespace-nowrap shadow-[var(--shadow-lift)]"
          style={{ left: hover.x, top: hover.y, transform: "translate(-50%, calc(-100% - 8px))" }}
          aria-hidden
        >
          <p className="font-medium text-fg">
            {DAYS[hover.d]} · {hourLabel(hover.h)}–{hourLabel((hover.h + 1) % 24)}
          </p>
          <p className="text-fg-muted">
            <span className="font-num text-sm font-semibold text-fg">{cell[metric].toFixed(meta.digits)}</span> {meta.unit} · {formatInt(cell.rides)} rides
            {cell.rides < LOW_CONFIDENCE ? " · low confidence" : ""}
          </p>
        </div>
      ) : null}
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-fg-muted">
        {(["good", "mid", "bad"] as const).map((b) => (
          <span key={b} className="inline-flex items-center gap-1.5">
            <span className="size-3 rounded-[3px]" style={{ background: BAND_VAR[b].fill, opacity: 0.85 }} aria-hidden />
            {meta.legend[b]}
          </span>
        ))}
        <span className="inline-flex items-center gap-1.5">
          <span className="size-3 rounded-[3px] border border-line-strong" style={{ backgroundImage: "repeating-linear-gradient(135deg, transparent 0 3px, rgb(127 127 127 / 0.35) 3px 4px)" }} aria-hidden />
          Fewer than {LOW_CONFIDENCE} rides
        </span>
      </div>
    </div>
  );
}

export function AirNoiseView() {
  const { filters } = useCityFilters();
  const [metric, setMetric] = useState<Metric>("pm25");
  const res = useApi(() => getAirNoise(filters), [filters.period, filters.mode, filters.districts.join(",")]);
  const meta = META[metric];

  const stats = useMemo(() => {
    const grid = res.data;
    if (!grid?.length) return null;
    let peak = { d: 0, h: 0, v: -Infinity };
    let low = { d: 0, h: 7, v: Infinity };
    grid.forEach((row, d) =>
      row.forEach((c, h) => {
        if (c[metric] > peak.v) peak = { d, h, v: c[metric] };
        // cleanest moment among hours people actually ride
        if (h >= 7 && h <= 21 && c[metric] < low.v) low = { d, h, v: c[metric] };
      }),
    );
    const avg = (rows: AirNoiseCell[][], h: number) => rows.reduce((s, r) => s + r[h][metric], 0) / rows.length;
    const profile = Array.from({ length: 24 }, (_, h) => ({
      h,
      label: hourLabel(h),
      weekday: Math.round(avg(grid.slice(0, 5), h) * 10) / 10,
      weekend: Math.round(avg(grid.slice(5), h) * 10) / 10,
    }));
    const above = grid.flat().filter((c) => c[metric] > meta.thresholds[meta.thresholds.length - 1].y).length;
    const rush = (profile[8].weekday + profile[18].weekday) / 2;
    const night = (profile[3].weekday + profile[4].weekday) / 2;
    return { peak, low, profile, above, rushVsNight: rush - night };
  }, [res.data, metric, meta]);

  return (
    <div className="mx-auto max-w-[1480px] space-y-5 px-4 py-5 sm:px-6">
      <PageHeader
        eyebrow={`Air & noise · ${PERIOD_LABEL[filters.period]}`}
        title="When the air and the noise peak"
        description="Average PM2.5 and sound level measured at handlebar height on the street, by weekday and hour. Weighted by the number of rides in each cell."
      >
        <Segmented
          value={metric}
          onChange={setMetric}
          label="Measure"
          options={[
            { value: "pm25", label: "PM2.5" },
            { value: "db", label: "Noise" },
          ]}
        />
      </PageHeader>

      {res.error ? (
        <ErrorState error={res.error} onRetry={res.retry} />
      ) : !res.data ? (
        <div className="space-y-5" aria-busy="true" aria-label="Loading air and noise data">
          <Skeleton className="h-[360px] rounded-2xl" />
          <Skeleton className="h-64 rounded-2xl" />
        </div>
      ) : !res.data.length || !stats ? (
        <EmptyState title="No measurements for this selection" body="Fewer than 5 riders recorded air and noise here in the period." />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            {[
              { k: "Peak", v: `${stats.peak.v.toFixed(meta.digits)} ${meta.unit}`, s: `${DAYS[stats.peak.d]}s at ${hourLabel(stats.peak.h)}` },
              { k: metric === "pm25" ? "Cleanest riding hour" : "Quietest riding hour", v: `${stats.low.v.toFixed(meta.digits)} ${meta.unit}`, s: `${DAYS[stats.low.d]}s at ${hourLabel(stats.low.h)}` },
              { k: "Rush hour vs night", v: `+${stats.rushVsNight.toFixed(meta.digits)} ${meta.unit}`, s: "08:00 & 18:00 vs 03:00–05:00, weekdays" },
              { k: `Hours above ${meta.thresholds[meta.thresholds.length - 1].y}`, v: `${stats.above} of 168`, s: metric === "pm25" ? "WHO 24 h guideline" : "High exposure threshold" },
            ].map((t) => (
              <div key={t.k} className="rounded-2xl border border-line bg-surface p-4">
                <p className="label-mono text-fg-subtle">{t.k}</p>
                <p className="mt-2 font-num text-2xl font-semibold tracking-tight text-fg">{t.v}</p>
                <p className="mt-1 text-xs text-fg-muted">{t.s}</p>
              </div>
            ))}
          </div>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>
                  {meta.label} by hour and weekday
                </CardTitle>
                <p className="mt-0.5 text-xs text-fg-muted">Hover a cell for the exact value and the number of rides behind it</p>
              </div>
            </CardHeader>
            <CardContent>
              <Heatmap grid={res.data} metric={metric} />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <div>
                <CardTitle>Daily profile</CardTitle>
                <p className="mt-0.5 text-xs text-fg-muted">Weekdays vs weekends, with the reference thresholds</p>
              </div>
            </CardHeader>
            <CardContent>
              <figure aria-label={`${meta.label} through the day: weekdays peak at ${stats.profile.reduce((a, b) => (b.weekday > a.weekday ? b : a)).label}.`}>
                <div className="h-64" aria-hidden>
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={stats.profile} margin={{ top: 8, right: 8, bottom: 0, left: -8 }}>
                      <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
                      <XAxis dataKey="h" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--fg-subtle)", fontFamily: "var(--font-mono)" }} tickFormatter={(h: number) => String(h).padStart(2, "0")} interval={2} />
                      <YAxis tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--fg-subtle)", fontFamily: "var(--font-mono)" }} width={44} domain={metric === "pm25" ? [0, "auto"] : [45, "auto"]} />
                      <Tooltip
                        cursor={{ stroke: "var(--fg)", strokeOpacity: 0.3 }}
                        isAnimationActive={false}
                        content={({ active, payload }) =>
                          active && payload?.length ? (
                            <div className="rounded-xl border border-line bg-surface px-3 py-2 text-xs shadow-[var(--shadow-lift)]">
                              <p className="font-medium text-fg">{hourLabel(Number(payload[0].payload.h))}</p>
                              <p className="text-fg-muted">
                                Weekdays <span className="font-num font-semibold text-fg">{payload[0].payload.weekday}</span> · weekends{" "}
                                <span className="font-num font-semibold text-fg">{payload[0].payload.weekend}</span> {meta.unit}
                              </p>
                            </div>
                          ) : null
                        }
                      />
                      {meta.thresholds.map((t) => (
                        <ReferenceLine key={t.y} y={t.y} stroke={t.color} strokeDasharray="5 4" ifOverflow="extendDomain" />
                      ))}
                      <Line dataKey="weekday" stroke="var(--color-signal)" strokeWidth={2.2} dot={false} isAnimationActive={false} />
                      <Line dataKey="weekend" stroke="var(--color-lane-300)" strokeWidth={2} strokeDasharray="1 0" dot={false} isAnimationActive={false} />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <figcaption className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-fg-muted">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-0.5 w-4 rounded bg-signal" aria-hidden /> Weekdays
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-0.5 w-4 rounded bg-lane-300" aria-hidden /> Weekends
                  </span>
                  {meta.thresholds.map((t) => (
                    <span key={t.y} className="inline-flex items-center gap-1.5">
                      <svg width="16" height="4" aria-hidden>
                        <line x1="0" y1="2" x2="16" y2="2" stroke={t.color} strokeWidth="2" strokeDasharray="4 3" />
                      </svg>
                      {t.label}
                    </span>
                  ))}
                </figcaption>
              </figure>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
