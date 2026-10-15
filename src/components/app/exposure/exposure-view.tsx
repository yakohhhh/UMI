"use client";

import { ArrowRight, Eye, Lightbulb, TrendingDown, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { ErrorState } from "@/components/data/states";
import { KpiTile } from "@/components/data/kpi-tile";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Segmented } from "@/components/ui/segmented";
import { Skeleton } from "@/components/ui/skeleton";
import { getExposure } from "@/lib/api";
import { formatInt } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";
import type { ExposureSummary, Kpi } from "@/lib/types";
import { cn } from "@/lib/utils";
import { CalendarHeatmap, type HeatMetric } from "./calendar-heatmap";
import { ExposureChart } from "./exposure-chart";

const TONE: Record<ExposureSummary["insights"][number]["tone"], { icon: LucideIcon; className: string; label: string }> = {
  good: { icon: TrendingDown, className: "bg-good-fill/15 text-good", label: "Improving" },
  watch: { icon: Eye, className: "bg-signal/15 text-accent-ink", label: "Worth watching" },
  neutral: { icon: Lightbulb, className: "bg-surface-2 text-fg-muted", label: "Good to know" },
};

const pmColor = (v: number) => (v <= 10 ? "var(--good-fill)" : v <= 15 ? "var(--mid-fill)" : "var(--bad-fill)");
const dbColor = (v: number) => (v <= 58 ? "var(--good-fill)" : v <= 64 ? "var(--mid-fill)" : "var(--bad-fill)");

function ExposureSkeleton() {
  return (
    <div className="space-y-6" aria-busy="true" aria-label="Loading your exposure">
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <Skeleton key={i} className="h-36 rounded-2xl" />
        ))}
      </div>
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Skeleton className="h-80 rounded-2xl" />
        <Skeleton className="h-80 rounded-2xl" />
      </div>
      <Skeleton className="h-56 rounded-2xl" />
    </div>
  );
}

function Content({ data }: { data: ExposureSummary }) {
  const [period, setPeriod] = useState<"weekly" | "monthly">("weekly");
  const [heat, setHeat] = useState<HeatMetric>("pm25");
  const { thresholds: th, totals } = data;
  const series = period === "weekly" ? data.weekly : data.monthly;

  const kpis = useMemo((): Kpi[] => {
    const weeklyPm = data.weekly.map((w) => w.pm25 ?? 0);
    return [
      {
        id: "pm",
        label: "PM2.5 while riding",
        value: totals.avgPm25,
        unit: "µg/m³",
        delta: totals.changePct,
        deltaUnit: "%",
        deltaLabel: "vs last winter",
        better: "down",
        spark: weeklyPm,
        limit: th.eu2030Pm25,
        limitLabel: "EU 2030 limit",
      },
      {
        id: "db",
        label: "Noise while riding",
        value: totals.avgDb,
        unit: "dB(A)",
        delta: totals.dbChange,
        deltaUnit: "dB",
        deltaLabel: "vs previous 4 weeks",
        better: "down",
        spark: data.weekly.map((w) => w.db ?? 0),
        limit: th.whoRoadNoise,
        limitLabel: "WHO road-traffic guideline",
      },
      {
        id: "hours",
        label: "Time in the saddle",
        value: totals.rideHours,
        unit: "h · 12 months",
        delta: Math.round(((data.weekly.slice(-4).reduce((s, w) => s + w.rideMin, 0) - data.weekly.slice(-8, -4).reduce((s, w) => s + w.rideMin, 0)) / 60) * 10) / 10,
        deltaUnit: "h",
        deltaLabel: "vs previous 4 weeks",
        better: "up",
        spark: data.weekly.map((w) => w.rideMin),
      },
      {
        id: "days",
        label: "Riding days",
        value: totals.ridingDays,
        unit: "of 365",
        delta: data.days.slice(-30).filter((d) => d.rideMin > 0).length - data.days.slice(-60, -30).filter((d) => d.rideMin > 0).length,
        deltaUnit: "days",
        deltaLabel: "last 30 days vs the 30 before",
        better: "up",
        spark: data.monthly.map((m) => m.rideMin),
      },
    ];
  }, [data, th, totals]);

  return (
    <div className="space-y-6">
      <div className="scrollbar-none -mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-1 sm:mx-0 sm:grid sm:grid-cols-2 sm:gap-4 sm:overflow-visible sm:px-0 sm:pb-0 xl:grid-cols-4">
        {kpis.map((k) => (
          <KpiTile key={k.id} kpi={k} className="w-[78%] shrink-0 snap-start sm:w-auto" />
        ))}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="font-display text-xl font-semibold tracking-tight">{period === "weekly" ? "Last 16 weeks" : "Last 12 months"}</h2>
        <Segmented
          value={period}
          onChange={setPeriod}
          label="Chart period"
          options={[
            { value: "weekly", label: "Weekly" },
            { value: "monthly", label: "Monthly" },
          ]}
        />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>PM2.5 while riding</CardTitle>
              <p className="mt-0.5 text-xs text-fg-muted">Average concentration, weighted by riding time</p>
            </div>
          </CardHeader>
          <CardContent className="pt-4">
            <ExposureChart
              data={series}
              dataKey="pm25"
              unit="µg/m³"
              digits={1}
              domain={[0, 24]}
              ticks={[0, 5, 10, 15, 20]}
              colorFor={pmColor}
              label="PM2.5 while riding"
              thresholds={[
                { y: th.whoPm25Annual, label: "WHO annual", color: "var(--good-fill)" },
                { y: th.eu2030Pm25, label: "EU 2030 limit", color: "var(--fg-muted)" },
                { y: th.whoPm25Daily, label: "WHO 24 h", color: "var(--bad-fill)" },
              ]}
            />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Noise while riding</CardTitle>
              <p className="mt-0.5 text-xs text-fg-muted">Average sound level at the handlebar, dB(A)</p>
            </div>
          </CardHeader>
          <CardContent className="pt-4">
            <ExposureChart
              data={series}
              dataKey="db"
              unit="dB(A)"
              digits={1}
              domain={[45, 70]}
              ticks={[45, 50, 55, 60, 65, 70]}
              colorFor={dbColor}
              label="Noise while riding"
              thresholds={[
                { y: th.whoRoadNoise, label: "WHO road traffic", color: "var(--good-fill)" },
                { y: 65, label: "High exposure", color: "var(--bad-fill)" },
              ]}
            />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="flex-wrap gap-3">
          <div>
            <CardTitle>Your year on the bike</CardTitle>
            <p className="mt-0.5 text-xs text-fg-muted">
              {formatInt(totals.ridingDays)} riding days · hover a day for details
            </p>
          </div>
          <Segmented
            size="sm"
            value={heat}
            onChange={setHeat}
            label="Calendar metric"
            options={[
              { value: "pm25", label: "PM2.5" },
              { value: "db", label: "Noise" },
              { value: "rideMin", label: "Riding time" },
            ]}
          />
        </CardHeader>
        <CardContent className="pt-5">
          <CalendarHeatmap days={data.days} metric={heat} />
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <section aria-labelledby="insights">
          <h2 id="insights" className="font-display text-xl font-semibold tracking-tight">
            Insights
          </h2>
          <ul className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
            {data.insights.map((i) => {
              const tone = TONE[i.tone];
              return (
                <li key={i.id} className="rounded-2xl border border-line bg-surface p-4">
                  <div className="flex items-center gap-2">
                    <span className={cn("flex size-8 items-center justify-center rounded-xl", tone.className)} aria-hidden>
                      <tone.icon className="size-4" />
                    </span>
                    <span className="label-mono text-[10px] text-fg-subtle">{tone.label}</span>
                  </div>
                  <h3 className="mt-3 text-[15px] leading-snug font-semibold text-fg">{i.title}</h3>
                  <p className="mt-1 text-sm leading-6 text-fg-muted">{i.body}</p>
                </li>
              );
            })}
          </ul>
        </section>
        <Card className="self-start">
          <CardHeader>
            <div>
              <CardTitle>Where your dose comes from</CardTitle>
              <p className="mt-0.5 text-xs text-fg-muted">Share of your PM2.5 dose, last 90 days</p>
            </div>
          </CardHeader>
          <CardContent className="space-y-4 pt-4">
            {data.contributors.map((c) => (
              <div key={c.street}>
                <div className="flex items-baseline justify-between gap-3 text-sm">
                  <Link href={`/app/map?q=${encodeURIComponent(c.street)}&metric=air`} className="truncate font-medium text-fg hover:text-accent-ink">
                    {c.street}
                  </Link>
                  <span className="font-num font-semibold">{Math.round(c.share * 100)}%</span>
                </div>
                <div className="mt-1.5 h-1.5 rounded-full bg-surface-2" aria-hidden>
                  <div className="h-full rounded-full" style={{ width: `${c.share * 100}%`, background: pmColor(c.pm25) }} />
                </div>
                <p className="mt-1 text-xs text-fg-muted">
                  {c.pm25.toFixed(1)} µg/m³ on average · {c.minutesWeek} min a week
                </p>
              </div>
            ))}
            <Link href="/app/routes" className="inline-flex items-center gap-1.5 text-sm font-medium text-accent-ink hover:underline">
              Find a cleaner commute <ArrowRight className="size-4" />
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

export function ExposureView() {
  const { data, error, retry } = useApi(getExposure);
  return (
    <div className="mx-auto max-w-[1180px] space-y-6 px-4 py-6 sm:px-6 lg:py-8">
      <header>
        <p className="label-mono text-accent-ink">Your exposure</p>
        <h1 className="mt-1.5 font-display text-3xl font-semibold tracking-tight sm:text-4xl">What you breathe and hear on the bike</h1>
        <p className="mt-2 max-w-2xl text-fg-muted">
          Measured by your Clip every 10 seconds while you ride, compared with the WHO guidelines and the EU limit that applies from 2030.
        </p>
      </header>
      {error ? <ErrorState error={error} onRetry={retry} /> : data ? <Content data={data} /> : <ExposureSkeleton />}
    </div>
  );
}
