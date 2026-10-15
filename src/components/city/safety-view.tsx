"use client";

import dynamic from "next/dynamic";
import { useMemo, useState } from "react";
import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Delta } from "@/components/data/delta";
import { EmptyState, ErrorState } from "@/components/data/states";
import { StatTile } from "@/components/data/stat-tile";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { ACTIVE_HOTSPOT_PER_WEEK, getCitySafety } from "@/lib/api";
import { formatInt, formatMonth, hourLabel } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";
import { cn } from "@/lib/utils";
import { PERIOD_LABEL, useCityFilters } from "./city-filters";
import { hotspotRadius } from "./hotspot-scale";
import { PageHeader } from "./page-header";

const HotspotMap = dynamic(() => import("./hotspot-map"), { ssr: false, loading: () => <Skeleton className="size-full rounded-none" /> });

function MonthTooltip({ active, payload }: { active?: boolean; payload?: { payload: { label: string; hardBrakes: number; rate: number; rides: number } }[] }) {
  if (!active || !payload?.length) return null;
  const p = payload[0].payload;
  return (
    <div className="rounded-xl border border-line bg-surface px-3 py-2 text-xs shadow-[var(--shadow-lift)]">
      <p className="font-medium text-fg">{p.label}</p>
      <p className="text-fg-muted">
        <span className="font-num font-semibold text-fg">{formatInt(p.hardBrakes)}</span> hard brakes · <span className="font-num text-fg">{formatInt(p.rides)}</span> rides
      </p>
      <p className="text-fg-muted">
        <span className="font-num font-semibold text-fg">{p.rate.toFixed(1)}</span> per 1,000 rides
      </p>
    </div>
  );
}

export function SafetyView() {
  const { filters } = useCityFilters();
  const safety = useApi(() => getCitySafety(filters), [filters.period, filters.mode, filters.districts.join(",")]);
  const [active, setActive] = useState<string | null>(null);

  const top = useMemo(() => [...(safety.data?.hotspots ?? [])].sort((a, b) => b.hardBrakes30d - a.hardBrakes30d).slice(0, 10), [safety.data]);
  const monthly = useMemo(
    () => (safety.data?.monthly ?? []).map((m) => ({ ...m, label: formatMonth(m.month), rate: m.rides ? (m.hardBrakes / m.rides) * 1000 : 0 })),
    [safety.data],
  );
  const max = Math.max(1, ...(safety.data?.hotspots ?? []).map((h) => h.hardBrakes30d));
  const d = safety.data;

  return (
    <div className="mx-auto max-w-[1480px] space-y-5 px-4 py-5 sm:px-6">
      <PageHeader
        eyebrow={`Safety · ${PERIOD_LABEL[filters.period]}`}
        title="Where riders brake hard"
        description="Decelerations above 3 m/s², clustered at junctions. Circle area is proportional to the number of hard brakes; hover a junction for its peak hour."
      />

      {safety.error ? (
        <ErrorState error={safety.error} onRetry={safety.retry} />
      ) : !d ? (
        <div className="space-y-5" aria-busy="true" aria-label="Loading safety data">
          <Skeleton className="h-24 rounded-2xl" />
          <Skeleton className="h-[520px] rounded-2xl" />
        </div>
      ) : d.hotspots.length === 0 ? (
        <EmptyState title="No hard-brake hotspot in this selection" body="Fewer than 5 riders braked hard at the same junction in the period. Widen the period or the districts." />
      ) : (
        <>
          <Card>
            <CardContent className="grid grid-cols-2 gap-x-6 gap-y-4 pt-5 lg:grid-cols-4">
              <StatTile label="Hard brakes" value={formatInt(d.totals.hardBrakes)} sub="Decelerations above 3 m/s²" />
              <StatTile label="Per 1,000 rides" value={d.totals.perThousandRides.toFixed(1)} sub={<Delta value={d.totals.delta} unit="%" better="down" suffix="vs previous period" />} />
              <StatTile label="Active hotspots" value={d.totals.activeHotspots} sub={`of ${d.hotspots.length} clusters · ${ACTIVE_HOTSPOT_PER_WEEK}+ hard brakes a week`} />
              <StatTile label="At hotspots" value={`${d.totals.atHotspotsPct}%`} sub="of all hard brakes happen at these junctions" />
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_460px]">
            <Card className="overflow-hidden">
              <div className="h-[440px] sm:h-[520px]">
                <HotspotMap hotspots={d.hotspots} activeId={active} onActive={setActive} />
              </div>
              <div className="flex flex-wrap items-end gap-5 border-t border-line px-5 py-3 text-xs text-fg-muted" aria-hidden>
                <span>Hard brakes</span>
                {[Math.round(max / 8), Math.round(max / 2), max].map((n) => {
                  const r = hotspotRadius(n, max);
                  return (
                    <span key={n} className="inline-flex items-center gap-2">
                      <span className="rounded-full border border-signal bg-signal/30" style={{ width: r * 2 * 0.6, height: r * 2 * 0.6 }} />
                      <span className="font-num">{n}</span>
                    </span>
                  );
                })}
              </div>
            </Card>

            <Card>
              <CardHeader>
                <div>
                  <CardTitle>Top 10 junctions</CardTitle>
                  <p className="mt-0.5 text-xs text-fg-muted">Hover a row to find it on the map</p>
                </div>
              </CardHeader>
              <CardContent className="px-2 pt-2">
                <table className="w-full text-left text-[13px]">
                  <caption className="sr-only">The ten junctions with the most hard brakes, {PERIOD_LABEL[filters.period]}</caption>
                  <thead>
                    <tr className="label-mono text-[10px] text-fg-subtle">
                      <th scope="col" className="w-8 px-2 py-2 font-normal">
                        #
                      </th>
                      <th scope="col" className="px-2 py-2 font-normal">
                        Junction
                      </th>
                      <th scope="col" className="px-2 py-2 text-right font-normal">
                        Brakes
                      </th>
                      <th scope="col" className="hidden px-2 py-2 text-right font-normal sm:table-cell">
                        Peak
                      </th>
                      <th scope="col" className="px-2 py-2 text-right font-normal">
                        Trend
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {top.map((h, i) => (
                      <tr
                        key={h.id}
                        tabIndex={0}
                        onMouseEnter={() => setActive(h.id)}
                        onMouseLeave={() => setActive(null)}
                        onFocus={() => setActive(h.id)}
                        onBlur={() => setActive(null)}
                        className={cn("border-t border-line outline-none transition-colors focus-visible:bg-surface-2 focus-visible:shadow-[inset_0_0_0_2px_var(--color-signal)]", active === h.id && "bg-surface-2")}
                      >
                        <td className="px-2 py-2.5 font-mono text-[11px] text-fg-subtle">{i + 1}</td>
                        <td className="px-2 py-2.5">
                          <p className="line-clamp-1 font-medium text-fg">{h.label}</p>
                          <p className="text-[11px] text-fg-muted">avg {h.avgDecel.toFixed(1)} m/s²</p>
                        </td>
                        <td className="px-2 py-2.5 text-right font-num font-semibold">{h.hardBrakes30d}</td>
                        <td className="hidden px-2 py-2.5 text-right font-num text-fg-muted sm:table-cell">{hourLabel(h.peakHour)}</td>
                        <td className="px-2 py-2.5 text-right">
                          <Delta value={h.trend} unit="%" better="down" suffix="" />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader className="flex-wrap gap-3">
              <div>
                <CardTitle>Hard brakes per month</CardTitle>
                <p className="mt-0.5 text-xs text-fg-muted">Bars: total hard brakes · line: per 1,000 rides, which corrects for the growing number of riders</p>
              </div>
            </CardHeader>
            <CardContent>
              <figure
                aria-label={`Hard brakes per month, from ${monthly[0]?.label} to ${monthly[monthly.length - 1]?.label}. The rate per 1,000 rides went from ${monthly[0]?.rate.toFixed(0)} to ${monthly[monthly.length - 1]?.rate.toFixed(0)}.`}
              >
                <div className="h-64" aria-hidden>
                  <ResponsiveContainer width="100%" height="100%">
                    <ComposedChart data={monthly} margin={{ top: 8, right: 0, bottom: 0, left: -8 }}>
                      <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
                      <XAxis dataKey="label" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--fg-subtle)" }} />
                      <YAxis yAxisId="n" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--fg-subtle)", fontFamily: "var(--font-mono)" }} width={44} />
                      <YAxis yAxisId="r" orientation="right" tickLine={false} axisLine={false} tick={{ fontSize: 11, fill: "var(--fg-subtle)", fontFamily: "var(--font-mono)" }} width={40} domain={[0, "auto"]} />
                      <Tooltip cursor={{ fill: "var(--surface-2)", opacity: 0.6 }} content={<MonthTooltip />} isAnimationActive={false} />
                      <Bar yAxisId="n" dataKey="hardBrakes" fill="var(--color-signal)" fillOpacity={0.75} radius={[4, 4, 1, 1]} maxBarSize={34} isAnimationActive={false} />
                      <Line yAxisId="r" dataKey="rate" stroke="var(--good-fill)" strokeWidth={2} dot={{ r: 2.5, fill: "var(--good-fill)" }} isAnimationActive={false} />
                    </ComposedChart>
                  </ResponsiveContainer>
                </div>
                <figcaption className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-xs text-fg-muted">
                  <span className="inline-flex items-center gap-1.5">
                    <span className="size-2.5 rounded-sm bg-signal/75" aria-hidden /> Hard brakes (left axis)
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span className="h-0.5 w-4 rounded bg-good-fill" aria-hidden /> Per 1,000 rides (right axis)
                  </span>
                </figcaption>
              </figure>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
