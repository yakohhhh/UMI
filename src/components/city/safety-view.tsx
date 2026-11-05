"use client";

import { CalendarClock, CircleCheckBig, Download, Ellipsis, Flag, Inbox, Send, type LucideIcon } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useRef, useState } from "react";
import { Bar, CartesianGrid, ComposedChart, Line, ResponsiveContainer, Tooltip as ChartTooltip, XAxis, YAxis } from "recharts";
import { BUCKET_META, CAUSE_META, HAZARD_META } from "@/components/app/ride-events";
import { Delta } from "@/components/data/delta";
import { EmptyState, ErrorState } from "@/components/data/states";
import { StatTile } from "@/components/data/stat-tile";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip } from "@/components/ui/tooltip";
import { ACTIVE_HOTSPOT_PER_WEEK, getCityHazards, getCitySafety } from "@/lib/api";
import { downloadFile, toCsv } from "@/lib/download";
import { formatDay, formatInt, formatMonth, hourLabel } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";
import { usePrefersReducedMotion } from "@/lib/hooks/use-media-query";
import { mockNow } from "@/lib/mock";
import { CAUSE_BUCKET, CITY_MIN_RIDERS } from "@/lib/reports";
import type { BrakeCause, BrakeHotspot, CityHazard } from "@/lib/types";
import { cn } from "@/lib/utils";
import { PERIOD_LABEL, useCityFilters } from "./city-filters";
import { hotspotRadius } from "./hotspot-scale";
import { PageHeader } from "./page-header";

const HotspotMap = dynamic(() => import("./hotspot-map"), { ssr: false, loading: () => <Skeleton className="size-full rounded-none" /> });

type CityCause = BrakeCause | "other";
type CauseShare = NonNullable<BrakeHotspot["causes"]>[number];

/**
 * One fixed colour per cause, whatever the junction: signal steps = traffic, lane steps = street issue,
 * hatched = other. Both four-step ramps pass the ordinal checks on the light and dark surfaces.
 */
const CAUSE_STYLE: Record<CityCause, { label: string; color: string }> = {
  vehicle: { label: "Vehicle cut across", color: "#b8360a" },
  pedestrian: { label: "Pedestrian", color: "#e8480f" },
  car_door: { label: "Car door", color: "#ff7a47" },
  animal: { label: "Animal", color: "#ff9e78" },
  junction: { label: "Junction or light", color: "#0f52b8" },
  lane_blocked: { label: "Lane blocked", color: "#2f7fff" },
  surface: { label: "Road surface", color: "#5e9cff" },
  roadworks: { label: "Roadworks", color: "#8cb8ff" },
  just_me: { label: "Just me", color: "transparent" }, // never published to the city
  other: { label: "Other", color: "transparent" },
};

/** Stacking order inside a bar: traffic, then street issues, then other, so buckets read as blocks. */
const CAUSE_ORDER: CityCause[] = ["vehicle", "pedestrian", "car_door", "animal", "junction", "lane_blocked", "surface", "roadworks", "other"];

const OTHER_FILL = "repeating-linear-gradient(135deg, var(--fg-subtle) 0 1.5px, transparent 1.5px 4px), var(--surface-3)";
const causeFill = (c: CityCause) => (c === "other" ? OTHER_FILL : CAUSE_STYLE[c].color);
const causeIcon = (c: CityCause): LucideIcon => (c === "other" ? Ellipsis : CAUSE_META[c].icon);
const pct = (share: number) => `${Math.round(share * 100)}%`;
const byShare = (causes: CauseShare[]) => [...causes].sort((a, b) => b.share - a.share || CAUSE_ORDER.indexOf(a.cause) - CAUSE_ORDER.indexOf(b.cause));

/** "Vehicle cut across 40%, pedestrian 20%, …" — the bar's text alternative. */
function describeCauses(causes: CauseShare[]) {
  return byShare(causes)
    .map((c, i) => `${i ? CAUSE_STYLE[c.cause].label.toLowerCase() : CAUSE_STYLE[c.cause].label} ${pct(c.share)}`)
    .join(", ");
}

/** City-side lifecycle of a published hazard: an icon and a word on every chip. */
const HAZARD_STATUS: Record<CityHazard["status"], { label: string; count: string; icon: LucideIcon; variant: BadgeProps["variant"] }> = {
  new: { label: "New", count: "new", icon: Inbox, variant: "signal" },
  sent_to_iris: { label: "Sent to IRIS", count: "sent to IRIS", icon: Send, variant: "outline" },
  scheduled: { label: "Scheduled", count: "scheduled", icon: CalendarClock, variant: "neutral" },
  fixed: { label: "Fixed", count: "fixed", icon: CircleCheckBig, variant: "lane" },
};

/** Day-level only, like the API: "14 Oct". */
const day = (d: string) => formatDay(`${d}T12:00:00Z`, { day: "numeric", month: "short" });

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

function CauseSwatch({ cause }: { cause: CityCause }) {
  return <span className={cn("size-2.5 shrink-0 rounded-[3px]", cause === "other" && "border border-line-strong")} style={{ background: causeFill(cause) }} aria-hidden />;
}

function CauseList({ causes }: { causes: CauseShare[] }) {
  return (
    <div className="min-w-44">
      <p className="label-mono text-[10px] text-fg-subtle">Why riders brake</p>
      <ul className="mt-1.5 space-y-1">
        {byShare(causes).map((c) => {
          const Icon = causeIcon(c.cause);
          return (
            <li key={c.cause} className="flex items-center gap-2">
              <CauseSwatch cause={c.cause} />
              <Icon className="size-3.5 shrink-0 text-fg-muted" aria-hidden />
              <span className="flex-1">{CAUSE_STYLE[c.cause].label}</span>
              <span className="font-num font-semibold">{pct(c.share)}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** Thin 100% stacked bar of a junction's causes; the exact mix is in its label and on hover. */
function CauseBar({ causes }: { causes: CauseShare[] }) {
  const parts = [...causes].sort((a, b) => CAUSE_ORDER.indexOf(a.cause) - CAUSE_ORDER.indexOf(b.cause));
  return (
    <Tooltip content={<CauseList causes={causes} />} side="left">
      <div role="img" aria-label={`Why riders brake: ${describeCauses(causes)}.`} className="py-1.5">
        <div className="flex h-2 w-full gap-0.5">
          {parts.map((p, i) => (
            <span
              key={p.cause}
              className={cn("h-full min-w-1", i === 0 && "rounded-l-[3px]", i === parts.length - 1 && "rounded-r-[3px]")}
              style={{ flexGrow: p.share, flexBasis: 0, background: causeFill(p.cause) }}
            />
          ))}
        </div>
      </div>
    </Tooltip>
  );
}

function WhyCell({ h }: { h: BrakeHotspot }) {
  if (!h.causes?.length)
    return (
      <div>
        <div className="my-1.5 h-2 rounded-[3px] border border-dashed border-line-strong" aria-hidden />
        <p className="text-[11px] leading-4 text-fg-subtle">
          Not enough answers yet <span className="whitespace-nowrap">· under {CITY_MIN_RIDERS} riders</span>
        </p>
      </div>
    );
  const top = byShare(h.causes)[0];
  return (
    <div>
      <CauseBar causes={h.causes} />
      {/* the biggest cause in words, so the mix isn't hover-only; screen readers get the full mix from the bar */}
      <p className="flex items-center gap-1.5 text-[11px] leading-4 text-fg" aria-hidden>
        <CauseSwatch cause={top.cause} />
        <span className="min-w-0 truncate">{CAUSE_STYLE[top.cause].label}</span>
        <span className="font-num font-semibold">{pct(top.share)}</span>
      </p>
      <p className="text-[11px] leading-4 text-fg-muted">
        answered by <span className="font-num text-fg">{h.answeredBy ?? `${CITY_MIN_RIDERS}+`}</span> riders
      </p>
    </div>
  );
}

function CauseLegend({ causes }: { causes: CityCause[] }) {
  const groups = (["behaviour", "infrastructure"] as const).map((bucket) => ({
    bucket,
    items: causes.filter((c): c is BrakeCause => c !== "other" && CAUSE_BUCKET[c] === bucket),
  }));
  return (
    <div className="space-y-1.5 px-3 pb-2 text-[11px] text-fg-muted">
      {groups
        .filter((g) => g.items.length)
        .map((g) => (
          <p key={g.bucket} className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <span className="label-mono w-[86px] shrink-0 text-[10px] text-fg-subtle">{BUCKET_META[g.bucket].label}</span>
            {g.items.map((c) => {
              const Icon = causeIcon(c);
              return (
                <span key={c} className="inline-flex items-center gap-1.5">
                  <CauseSwatch cause={c} />
                  <Icon className="size-3 text-fg-subtle" aria-hidden />
                  {CAUSE_STYLE[c].label}
                </span>
              );
            })}
          </p>
        ))}
      {causes.includes("other") ? (
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1">
          <span className="label-mono w-[86px] shrink-0 text-[10px] text-fg-subtle">Other</span>
          <span className="inline-flex items-center gap-1.5">
            <CauseSwatch cause="other" />
            <Ellipsis className="size-3 text-fg-subtle" aria-hidden />
            Causes under 10%, grouped
          </span>
        </p>
      ) : null}
    </div>
  );
}

function HazardsCard() {
  const { filters } = useCityFilters();
  const hazards = useApi(() => getCityHazards(filters), [filters.period, filters.mode, filters.districts.join(",")]);
  const rows = useMemo(() => [...(hazards.data ?? [])].sort((a, b) => b.riders - a.riders), [hazards.data]);
  const maxRiders = Math.max(1, ...rows.map((h) => h.riders));
  const counts = useMemo(() => (Object.keys(HAZARD_STATUS) as CityHazard["status"][]).map((s) => ({ status: s, n: rows.filter((h) => h.status === s).length })).filter((c) => c.n > 0), [rows]);

  const exportIris = () => {
    const columns = ["hazard_id", "type", "type_label", "street", "district", "longitude", "latitude", "riders", "first_seen", "last_confirmed", "status"];
    const csv = toCsv(
      rows.map((h) => ({
        hazard_id: h.id,
        type: h.kind,
        type_label: HAZARD_META[h.kind].label,
        street: h.street,
        district: h.district,
        longitude: h.coordinates[0],
        latitude: h.coordinates[1],
        riders: h.riders,
        first_seen: h.firstSeen,
        last_confirmed: h.lastConfirmed,
        status: h.status,
      })),
      columns,
    );
    downloadFile(`umi-hazards-iris-${filters.period}-${mockNow().toISOString().slice(0, 10)}.csv`, csv, "text/csv;charset=utf-8");
  };

  return (
    <section id="hazards" aria-labelledby="hazards-title" className="scroll-mt-40">
      <Card>
        <CardHeader className="flex-wrap gap-3">
          <div className="min-w-0">
            <CardTitle id="hazards-title" className="flex items-center gap-2">
              <Flag className="size-4 text-fg-muted" aria-hidden /> Flagged by riders
            </CardTitle>
            <p className="mt-0.5 text-xs text-fg-muted">Published once {CITY_MIN_RIDERS} different riders flagged or confirmed it · day-level dates · never who.</p>
          </div>
          <Button variant="secondary" size="sm" onClick={exportIris} disabled={!rows.length}>
            <Download /> Export for IRIS
          </Button>
        </CardHeader>
        <CardContent className="px-2 pt-3">
          {hazards.error ? (
            <ErrorState error={hazards.error} onRetry={hazards.retry} compact className="mx-3" />
          ) : !hazards.data ? (
            <div className="space-y-2 px-3" aria-busy="true" aria-label="Loading rider-flagged hazards">
              {Array.from({ length: 5 }, (_, i) => (
                <Skeleton key={i} className="h-11" />
              ))}
            </div>
          ) : rows.length === 0 ? (
            <EmptyState
              icon={<Flag />}
              title="No rider-flagged hazard in this selection"
              body={`Nothing reached ${CITY_MIN_RIDERS} different riders in the period. Below that, a flag stays on riders' own maps until enough of them confirm it.`}
              className="mx-3"
            />
          ) : (
            <>
              <p className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 pb-2 text-xs text-fg-muted">
                <span>
                  <span className="font-num font-semibold text-fg">{rows.length}</span> {rows.length === 1 ? "hazard" : "hazards"}
                </span>
                {counts.map(({ status, n }) => {
                  const s = HAZARD_STATUS[status];
                  return (
                    <span key={status} className="inline-flex items-center gap-1">
                      <s.icon className="size-3.5 text-fg-subtle" aria-hidden />
                      <span className="font-num text-fg">{n}</span> {s.count}
                    </span>
                  );
                })}
              </p>
              <div className="overflow-x-auto" role="region" aria-labelledby="hazards-title" tabIndex={0}>
                <table className="w-full min-w-[600px] text-left text-[13px]">
                  <caption className="sr-only">Hazards flagged by at least {CITY_MIN_RIDERS} different riders, {PERIOD_LABEL[filters.period]}, most riders first</caption>
                  <thead>
                    <tr className="label-mono text-[10px] text-fg-subtle">
                      <th scope="col" className="px-3 py-2 font-normal">
                        Hazard
                      </th>
                      <th scope="col" className="px-3 py-2 font-normal">
                        Street
                      </th>
                      <th scope="col" className="hidden px-3 py-2 font-normal lg:table-cell">
                        District
                      </th>
                      <th scope="col" className="px-3 py-2 text-right font-normal">
                        Riders
                      </th>
                      <th scope="col" className="hidden px-3 py-2 font-normal md:table-cell">
                        First seen
                      </th>
                      <th scope="col" className="px-3 py-2 font-normal">
                        Last confirmed
                      </th>
                      <th scope="col" className="px-3 py-2 font-normal">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map((h) => {
                      const k = HAZARD_META[h.kind];
                      const s = HAZARD_STATUS[h.status];
                      return (
                        <tr key={h.id} className="border-t border-line">
                          <td className="px-3 py-2.5">
                            <span className="inline-flex items-center gap-2 whitespace-nowrap">
                              <span className="flex size-7 shrink-0 items-center justify-center rounded-lg text-fg" style={{ background: `color-mix(in srgb, ${k.color} 22%, transparent)` }} aria-hidden>
                                <k.icon className="size-3.5" />
                              </span>
                              <span className="font-medium text-fg">{k.label}</span>
                            </span>
                          </td>
                          <td className="px-3 py-2.5">
                            <p className="text-fg">{h.street}</p>
                            <p className="text-[11px] text-fg-muted lg:hidden">{h.district}</p>
                          </td>
                          <td className="hidden px-3 py-2.5 text-fg-muted lg:table-cell">{h.district}</td>
                          <td className="px-3 py-2.5">
                            <div className="flex items-center justify-end gap-2">
                              <div className="hidden h-1.5 w-14 rounded-full bg-surface-2 sm:block" aria-hidden>
                                <div className="h-full rounded-full bg-lane" style={{ width: `${(h.riders / maxRiders) * 100}%` }} />
                              </div>
                              <span className="w-6 text-right font-num font-semibold">{h.riders}</span>
                            </div>
                          </td>
                          <td className="hidden px-3 py-2.5 whitespace-nowrap text-fg-muted md:table-cell">
                            <time dateTime={h.firstSeen}>{day(h.firstSeen)}</time>
                          </td>
                          <td className="px-3 py-2.5 whitespace-nowrap text-fg-muted">
                            <time dateTime={h.lastConfirmed}>{day(h.lastConfirmed)}</time>
                          </td>
                          <td className="px-3 py-2.5">
                            <Badge variant={s.variant} size="sm">
                              <s.icon aria-hidden /> {s.label}
                            </Badge>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
              <p className="mt-3 px-3 text-[11px] leading-4 text-fg-subtle">
                New = not in IRIS yet · Scheduled = a repair date is set · Fixed = the Clips measured the repair. Riders who flagged it hear back; the city never learns who they are.
              </p>
            </>
          )}
        </CardContent>
      </Card>
    </section>
  );
}

export function SafetyView() {
  const { filters } = useCityFilters();
  const safety = useApi(() => getCitySafety(filters), [filters.period, filters.mode, filters.districts.join(",")]);
  const [active, setActive] = useState<string | null>(null);
  const reduceMotion = usePrefersReducedMotion();

  const top = useMemo(() => [...(safety.data?.hotspots ?? [])].sort((a, b) => b.hardBrakes30d - a.hardBrakes30d).slice(0, 10), [safety.data]);
  const topCauses = useMemo(() => CAUSE_ORDER.filter((c) => top.some((h) => h.causes?.some((x) => x.cause === c))), [top]);
  const monthly = useMemo(
    () => (safety.data?.monthly ?? []).map((m) => ({ ...m, label: formatMonth(m.month), rate: m.rides ? (m.hardBrakes / m.rides) * 1000 : 0 })),
    [safety.data],
  );
  const max = Math.max(1, ...(safety.data?.hotspots ?? []).map((h) => h.hardBrakes30d));
  const d = safety.data;

  // The overview's "flagged" alert links to #hazards; the page above it renders after its data, so scroll once it's laid out.
  const scrolled = useRef(false);
  useEffect(() => {
    if (scrolled.current || (!d && !safety.error) || window.location.hash !== "#hazards") return;
    scrolled.current = true;
    const id = window.requestAnimationFrame(() => document.getElementById("hazards")?.scrollIntoView({ behavior: reduceMotion ? "auto" : "smooth", block: "start" }));
    return () => window.cancelAnimationFrame(id);
  }, [d, safety.error, reduceMotion]);

  return (
    <div className="mx-auto max-w-[1480px] space-y-5 px-4 py-5 sm:px-6">
      <PageHeader
        eyebrow={`Safety · ${PERIOD_LABEL[filters.period]}`}
        title="Where riders brake hard"
        description="Decelerations above 3 m/s², clustered at junctions, with why riders say they braked. Circle area is proportional to the number of hard brakes; hover a junction for its peak hour and top causes."
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

          <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_560px] xl:items-start">
            <Card className="overflow-hidden">
              <div className="h-[440px] sm:h-[520px] xl:h-[600px]">
                <HotspotMap hotspots={d.hotspots} activeId={active} onActive={setActive} causeStyle={CAUSE_STYLE} />
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
              <CardContent className="px-2 pt-3">
                {topCauses.length ? <CauseLegend causes={topCauses} /> : null}
                <table className="w-full text-left text-[13px]">
                  <caption className="sr-only">The ten junctions with the most hard brakes, {PERIOD_LABEL[filters.period]}, with why riders brake there</caption>
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
                      <th scope="col" className="px-2 py-2 text-right font-normal">
                        Trend
                      </th>
                      <th scope="col" className="hidden w-[168px] px-2 py-2 font-normal sm:table-cell">
                        Why riders brake
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
                        <td className="px-2 py-2.5 align-top font-mono text-[11px] text-fg-subtle">{i + 1}</td>
                        <td className="px-2 py-2.5 align-top">
                          <p className="line-clamp-2 leading-snug font-medium text-fg">{h.label}</p>
                          <p className="mt-0.5 text-[11px] text-fg-muted">
                            avg {h.avgDecel.toFixed(1)} m/s² · peak <span className="font-num">{hourLabel(h.peakHour)}</span>
                          </p>
                          <div className="mt-1.5 sm:hidden">
                            <WhyCell h={h} />
                          </div>
                        </td>
                        <td className="px-2 py-2.5 text-right align-top font-num font-semibold">{h.hardBrakes30d}</td>
                        <td className="px-2 py-2.5 text-right align-top">
                          <Delta value={h.trend} unit="%" better="down" suffix="" />
                        </td>
                        <td className="hidden px-2 py-2 align-top sm:table-cell">
                          <WhyCell h={h} />
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="mt-3 px-2 text-[11px] leading-4 text-fg-subtle">
                  Riders answer after the ride. &ldquo;Just me&rdquo; answers are left out; causes under 10% are grouped as other; nothing is shown below {CITY_MIN_RIDERS} riders.
                </p>
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
                      <ChartTooltip cursor={{ fill: "var(--surface-2)", opacity: 0.6 }} content={<MonthTooltip />} isAnimationActive={false} />
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

      <HazardsCard />
    </div>
  );
}
