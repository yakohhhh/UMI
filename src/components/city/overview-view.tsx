"use client";

import { ArrowRight, ArrowUpRight, CircleAlert, CircleCheck, TriangleAlert, type LucideIcon } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useMemo, useState } from "react";
import { EmptyState, ErrorState } from "@/components/data/states";
import { KpiTile } from "@/components/data/kpi-tile";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Segmented } from "@/components/ui/segmented";
import { Skeleton } from "@/components/ui/skeleton";
import { getCityOverview, getDistrictsGeo } from "@/lib/api";
import { formatInt, formatRelative } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";
import { mockNow } from "@/lib/mock";
import { BAND_VAR } from "@/lib/score";
import type { CityAlert } from "@/lib/types";
import { cn } from "@/lib/utils";
import { PERIOD_LABEL, useCityFilters } from "./city-filters";
import { DISTRICT_METRICS, type DistrictMetric } from "./district-metrics";
import { PageHeader } from "./page-header";

const DistrictMap = dynamic(() => import("./district-map"), { ssr: false, loading: () => <Skeleton className="size-full rounded-none" /> });

const ALERT_ICON: Record<CityAlert["tone"], { icon: LucideIcon; className: string }> = {
  bad: { icon: TriangleAlert, className: "bg-bad-fill/15 text-bad" },
  mid: { icon: CircleAlert, className: "bg-mid-fill/20 text-mid" },
  good: { icon: CircleCheck, className: "bg-good-fill/15 text-good" },
};

export function OverviewView() {
  const { filters, toggleDistrict } = useCityFilters();
  const [metric, setMetric] = useState<DistrictMetric>("overall");
  const overview = useApi(() => getCityOverview(filters), [filters.period, filters.mode, filters.districts.join(",")]);
  const geo = useApi(getDistrictsGeo);
  const meta = DISTRICT_METRICS[metric];
  const ranked = useMemo(() => [...(overview.data?.districts ?? [])].sort(meta.worstFirst), [overview.data, meta]);
  const maxRides = Math.max(1, ...ranked.map((d) => d.ridesWeek));

  if (overview.error) {
    return (
      <div className="mx-auto max-w-[1480px] px-4 py-6 sm:px-6">
        <ErrorState error={overview.error} onRetry={overview.retry} />
      </div>
    );
  }
  const data = overview.data;

  return (
    <div className="mx-auto max-w-[1480px] space-y-5 px-4 py-5 sm:px-6">
      <PageHeader eyebrow={`Overview · ${PERIOD_LABEL[filters.period]}`} title="Barcelona's streets, as riders feel them">
        {data ? (
          <p className="text-xs text-fg-muted">
            Updated {formatRelative(data.generatedAt, mockNow())} · refreshed hourly
          </p>
        ) : null}
      </PageHeader>

      {!data ? (
        <div className="grid grid-cols-2 gap-4 md:grid-cols-3 xl:grid-cols-5" aria-busy="true" aria-label="Loading key figures">
          {[0, 1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-40 rounded-2xl" />
          ))}
        </div>
      ) : data.kpis.length === 0 ? (
        <EmptyState title="No data for this selection yet" body="Fewer than 5 riders crossed these streets in the period. Widen the period or the districts." />
      ) : (
        <section
          aria-label="Key figures"
          className="scrollbar-none -mx-4 flex snap-x snap-mandatory gap-3 overflow-x-auto px-4 pb-1 sm:mx-0 sm:grid sm:grid-cols-2 sm:gap-4 sm:overflow-visible sm:px-0 sm:pb-0 md:grid-cols-3 xl:grid-cols-5"
        >
          {data.kpis.map((k) => (
            <KpiTile key={k.id} kpi={k} className="w-[78%] shrink-0 snap-start sm:w-auto" />
          ))}
        </section>
      )}

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_440px]">
        <Card className="overflow-hidden">
          <CardHeader className="flex-wrap gap-3 pb-4">
            <div>
              <CardTitle>Districts</CardTitle>
              <p className="mt-0.5 text-xs text-fg-muted">{meta.label} · click a district to filter every page</p>
            </div>
            <Segmented
              size="sm"
              value={metric}
              onChange={setMetric}
              label="District map metric"
              options={(Object.keys(DISTRICT_METRICS) as DistrictMetric[]).map((m) => ({ value: m, label: DISTRICT_METRICS[m].short }))}
            />
          </CardHeader>
          <div className="h-[420px] border-y border-line sm:h-[480px]">
            {geo.data && data ? (
              <DistrictMap geo={geo.data} stats={data.districts} metric={metric} selected={filters.districts} onToggle={toggleDistrict} />
            ) : geo.error ? (
              <ErrorState error={geo.error} onRetry={geo.retry} compact className="m-4" />
            ) : (
              <Skeleton className="size-full rounded-none" />
            )}
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1.5 px-5 py-3 text-xs text-fg-muted">
            {(["good", "mid", "bad"] as const).map((b) => (
              <span key={b} className="inline-flex items-center gap-1.5">
                <span className="h-2.5 w-4 rounded-sm" style={{ background: BAND_VAR[b].fill, opacity: 0.8 }} aria-hidden />
                {meta.legend[b]}
              </span>
            ))}
          </div>
        </Card>

        <Card>
          <CardHeader>
            <div>
              <CardTitle>Ranking</CardTitle>
              <p className="mt-0.5 text-xs text-fg-muted">Needs attention first · {meta.short}</p>
            </div>
          </CardHeader>
          <CardContent className="px-2 pt-2">
            {!data ? (
              <div className="space-y-2 px-3">
                {Array.from({ length: 8 }, (_, i) => (
                  <Skeleton key={i} className="h-10" />
                ))}
              </div>
            ) : (
              <table className="w-full text-left text-[13px]">
                <caption className="sr-only">Districts ranked by {meta.label.toLowerCase()}, those needing attention first</caption>
                <thead>
                  <tr className="label-mono text-[10px] text-fg-subtle">
                    <th scope="col" className="px-3 py-2 font-normal">
                      District
                    </th>
                    <th scope="col" className="px-3 py-2 text-right font-normal">
                      {meta.short}
                    </th>
                    <th scope="col" className="hidden px-3 py-2 font-normal sm:table-cell">
                      Rides
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {ranked.map((d) => {
                    const on = filters.districts.includes(d.name);
                    const dim = filters.districts.length > 0 && !on;
                    return (
                      <tr key={d.name} className={cn("border-t border-line transition-colors", on && "bg-signal/[0.06]", dim && "text-fg-subtle")}>
                        <td className="px-3 py-2">
                          <button
                            type="button"
                            onClick={() => toggleDistrict(d.name)}
                            aria-pressed={on}
                            className="flex items-center gap-2 rounded text-left font-medium hover:text-accent-ink"
                          >
                            <span className="size-2 shrink-0 rounded-full" style={{ background: BAND_VAR[meta.band(d)].fill }} aria-hidden />
                            {d.name}
                          </button>
                        </td>
                        <td className="px-3 py-2 text-right font-num font-semibold">{meta.format(d)}</td>
                        <td className="hidden px-3 py-2 sm:table-cell">
                          <div className="flex items-center gap-2">
                            <div className="h-1.5 w-20 rounded-full bg-surface-2" aria-hidden>
                              <div className="h-full rounded-full bg-lane" style={{ width: `${(d.ridesWeek / maxRides) * 100}%` }} />
                            </div>
                            <span className="font-num text-xs text-fg-muted">{formatInt(d.ridesWeek)}</span>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Signals to act on</CardTitle>
            <p className="mt-0.5 text-xs text-fg-muted">Changes the data flagged since last week</p>
          </div>
        </CardHeader>
        <CardContent>
          {data ? (
            <ul className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
              {data.alerts.map((a) => {
                const tone = ALERT_ICON[a.tone];
                return (
                  <li key={a.id}>
                    <Link href={a.href} className="group flex h-full flex-col rounded-xl border border-line bg-surface-2/40 p-4 transition-colors hover:border-line-strong hover:bg-surface-2">
                      <span className={cn("flex size-8 items-center justify-center rounded-lg", tone.className)} aria-hidden>
                        <tone.icon className="size-4" />
                      </span>
                      <span className="mt-3 text-sm leading-snug font-semibold text-fg">{a.title}</span>
                      <span className="mt-1 flex-1 text-xs leading-5 text-fg-muted">{a.body}</span>
                      <span className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-accent-ink">
                        Open <ArrowRight className="size-3.5 transition-transform group-hover:translate-x-0.5" aria-hidden />
                      </span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          ) : (
            <Skeleton className="h-40" />
          )}
        </CardContent>
      </Card>

      <p className="flex items-center gap-1.5 text-[11px] text-fg-subtle">
        Methodology: scores aggregate at least 5 riders per street segment and hour.{" "}
        <Link href="/city/api#privacy" className="inline-flex items-center gap-0.5 text-accent-ink hover:underline">
          How we anonymise <ArrowUpRight className="size-3" aria-hidden />
        </Link>
      </p>
    </div>
  );
}
