"use client";

import { Bike, Check, Link2, Route, Search, ShieldCheck, X } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { Delta } from "@/components/data/delta";
import { DimensionIcon } from "@/components/score/dimension-icon";
import { ScoreBadge } from "@/components/score/score-badge";
import { ScoreRing } from "@/components/score/score-gauge";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatInt, formatKm, hourLabel, pluralize } from "@/lib/format";
import {
  BAND_VAR,
  DIMENSIONS,
  SCORE_DIMENSIONS,
  brakesFromSafetyScore,
  dbFromNoiseScore,
  pmFromAirScore,
  scoreBand,
  vibFromComfortScore,
  type ScoreBand,
} from "@/lib/score";
import { hourlyValues, scoreAt, scoreWindow, searchable } from "@/lib/street-geojson";
import type { MapMetric, ScoreDimension, StreetKind, StreetSegment } from "@/lib/types";
import { cn } from "@/lib/utils";

export const KIND_LABEL: Record<StreetKind, string> = {
  arterial: "Main road",
  boulevard: "Boulevard",
  street: "Street",
  green: "Green axis",
  promenade: "Promenade",
  seafront: "Seafront",
};

/** How the best / worst ends of each scale read in a list title. */
const SUPERLATIVE: Record<MapMetric, { best: string; worst: string; goodPhrase: string }> = {
  overall: { best: "Calmest right now", worst: "Worth avoiding", goodPhrase: "feel calm" },
  comfort: { best: "Smoothest surfaces", worst: "Roughest surfaces", goodPhrase: "ride smooth" },
  safety: { best: "Fewest hard brakes", worst: "Most hard brakes", goodPhrase: "feel safe" },
  air: { best: "Cleanest air", worst: "Most polluted", goodPhrase: "have clean air" },
  noise: { best: "Quietest", worst: "Loudest", goodPhrase: "are quiet" },
};

export function streetSpan(s: Pick<StreetSegment, "from" | "to">) {
  return [s.from, s.to].filter(Boolean).join(" → ");
}

// ------------------------------------------------------------------ shares

export interface BandShares {
  km: Record<ScoreBand, number>;
  pct: Record<ScoreBand, number>;
  totalKm: number;
}

/** Share of mapped street length in each score band at a given hour. */
export function bandShares(streets: StreetSegment[], metric: MapMetric, hour: number): BandShares {
  const m: Record<ScoreBand, number> = { good: 0, mid: 0, bad: 0 };
  for (const s of streets) m[scoreBand(scoreAt(s, metric, hour))] += s.lengthM;
  const total = m.good + m.mid + m.bad || 1;
  const good = Math.round((m.good / total) * 100);
  const mid = Math.round((m.mid / total) * 100);
  return {
    km: { good: m.good / 1000, mid: m.mid / 1000, bad: m.bad / 1000 },
    pct: { good, mid, bad: Math.max(0, 100 - good - mid) },
    totalKm: total / 1000,
  };
}

export function ShareBar({ shares, className }: { shares: BandShares; className?: string }) {
  return (
    <div className={cn("flex h-2 gap-0.5 overflow-hidden rounded-full", className)} aria-hidden>
      {(["good", "mid", "bad"] as const).map((b) =>
        shares.pct[b] > 0 ? <span key={b} className="h-full first:rounded-l-full last:rounded-r-full" style={{ width: `${shares.pct[b]}%`, background: BAND_VAR[b].fill }} /> : null,
      )}
    </div>
  );
}

// ------------------------------------------------------------------ hourly bars

/**
 * 24 bars, one per hour, coloured by band. Clicking a bar moves the hour
 * (the hour slider is the keyboard equivalent, so bars stay out of the tab order).
 */
export function HourlyBars({ values, hour, onHour, metric }: { values: number[]; hour: number; onHour: (h: number) => void; metric: MapMetric }) {
  const best = values.indexOf(Math.max(...values));
  const worst = values.indexOf(Math.min(...values));
  const meta = DIMENSIONS[metric];
  return (
    <figure aria-label={`${meta.label} score through the day: highest at ${hourLabel(best)} (${values[best]}), lowest at ${hourLabel(worst)} (${values[worst]}).`}>
      <div className="relative flex h-24 items-end gap-[3px]" aria-hidden>
        {[70, 45].map((y) => (
          <span key={y} className="pointer-events-none absolute inset-x-0 border-t border-dashed border-line-strong" style={{ bottom: `${y}%` }} />
        ))}
        {values.map((v, h) => (
          <button
            key={h}
            type="button"
            tabIndex={-1}
            onClick={() => onHour(h)}
            className="group relative h-full flex-1 cursor-pointer"
            title={`${hourLabel(h)} · ${v}`}
          >
            <span
              className="absolute inset-x-0 bottom-0 h-full origin-bottom rounded-t-[3px] transition-[transform,opacity] duration-300 ease-out-cubic group-hover:opacity-100"
              style={{ transform: `scaleY(${Math.max(4, v) / 100})`, background: BAND_VAR[scoreBand(v)].fill, opacity: h === hour ? 1 : 0.38 }}
            />
            {h === hour ? <span className="absolute -bottom-2 left-1/2 size-1 -translate-x-1/2 rounded-full bg-fg" /> : null}
          </button>
        ))}
      </div>
      <div className="mt-3 flex justify-between font-mono text-[10px] text-fg-subtle" aria-hidden>
        <span>00</span>
        <span>06</span>
        <span>12</span>
        <span>18</span>
        <span>23</span>
      </div>
    </figure>
  );
}

// ------------------------------------------------------------------ street details

function measureFor(dim: ScoreDimension, score: number) {
  switch (dim) {
    case "comfort":
      return `${vibFromComfortScore(score).toFixed(2)} m/s² RMS`;
    case "safety":
      return `${brakesFromSafetyScore(score)} brakes / 100 rides`;
    case "air":
      return `≈ ${pmFromAirScore(score).toFixed(1)} µg/m³ PM2.5`;
    case "noise":
      return `≈ ${dbFromNoiseScore(score)} dB(A)`;
  }
}

export function StreetDetails({
  street,
  metric,
  hour,
  onHourChange,
  onMetricChange,
  onClose,
}: {
  street: StreetSegment;
  metric: MapMetric;
  hour: number;
  onHourChange: (h: number) => void;
  onMetricChange: (m: MapMetric) => void;
  onClose?: () => void;
}) {
  const [copied, setCopied] = useState(false);
  const values = useMemo(() => hourlyValues(street, metric), [street, metric]);
  const score = values[hour];
  const band = scoreBand(score);
  const meta = DIMENSIONS[metric];
  const best = scoreWindow(values, "best");
  const worst = scoreWindow(values, "worst");
  const span = streetSpan(street);

  const copyLink = async () => {
    try {
      await navigator.clipboard.writeText(`${window.location.origin}/app/map?street=${street.id}&metric=${metric}&hour=${hour}`);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  };

  return (
    <article aria-labelledby={`street-${street.id}`} className="space-y-6">
      <header className="relative pr-10">
        <p className="label-mono text-[10px] text-fg-subtle">
          {KIND_LABEL[street.kind]} · {street.district}
        </p>
        <h2 id={`street-${street.id}`} className="mt-1.5 font-display text-2xl leading-tight font-semibold tracking-tight text-fg">
          {street.name}
        </h2>
        {span ? <p className="mt-1 text-sm text-fg-muted">{span}</p> : null}
        <div className="mt-3 flex flex-wrap gap-1.5">
          {street.bikeLane ? (
            <Badge variant="lane" size="sm">
              <Bike /> Protected bike lane
            </Badge>
          ) : (
            <Badge variant="outline" size="sm">
              <Bike /> Shared with traffic
            </Badge>
          )}
          <Badge variant="neutral" size="sm">
            {street.lengthM} m
          </Badge>
        </div>
        {onClose ? (
          <Button variant="ghost" size="icon-sm" onClick={onClose} aria-label="Close street details" className="absolute top-0 right-0">
            <X />
          </Button>
        ) : null}
      </header>

      <section className="flex items-center gap-4 rounded-2xl border border-line bg-surface p-4" aria-label={`${meta.label} at ${hourLabel(hour)}`}>
        <ScoreRing score={score} size={68} stroke={6} label={`${meta.label} score at ${hourLabel(hour)}: ${score} out of 100, ${meta.bands[band]}`} />
        <div className="min-w-0">
          <p className="flex items-center gap-1.5 text-xs text-fg-muted">
            <DimensionIcon metric={metric} className="size-3.5" /> {meta.label} at <span className="font-num font-semibold text-fg">{hourLabel(hour)}</span>
          </p>
          <p className="mt-0.5 font-display text-lg font-semibold" style={{ color: BAND_VAR[band].ink }}>
            {meta.bands[band]}
          </p>
          <p className="mt-0.5 text-xs text-fg-muted">
            Best between{" "}
            <button type="button" className="font-num font-semibold text-fg underline decoration-line-strong underline-offset-2 hover:decoration-fg" onClick={() => onHourChange(best.start)}>
              {hourLabel(best.start)}–{hourLabel(best.end)}
            </button>{" "}
            · avg {best.avg}
          </p>
        </div>
      </section>

      <section aria-labelledby={`street-${street.id}-dims`}>
        <h3 id={`street-${street.id}-dims`} className="text-xs font-medium text-fg-muted">
          All four scores at {hourLabel(hour)}
        </h3>
        <div className="mt-2 grid grid-cols-2 gap-2">
          {SCORE_DIMENSIONS.map((d) => {
            const v = street.hourly[d][hour];
            const b = scoreBand(v);
            const active = metric === d;
            return (
              <button
                key={d}
                type="button"
                aria-pressed={active}
                onClick={() => onMetricChange(active ? "overall" : d)}
                className={cn(
                  "rounded-xl border p-3 text-left transition-colors",
                  active ? "border-fg/40 bg-surface-2" : "border-line bg-surface hover:border-line-strong",
                )}
              >
                <span className="flex items-center gap-1.5 text-xs text-fg-muted">
                  <DimensionIcon metric={d} className="size-3.5" />
                  {DIMENSIONS[d].label}
                </span>
                <span className="mt-1 flex items-baseline gap-2">
                  <span className="font-num text-xl font-semibold text-fg">{v}</span>
                  <span className="text-[11px] font-medium" style={{ color: BAND_VAR[b].ink }}>
                    {DIMENSIONS[d].bands[b]}
                  </span>
                </span>
                <span className="mt-0.5 block truncate font-mono text-[10.5px] text-fg-subtle">{measureFor(d, v)}</span>
              </button>
            );
          })}
        </div>
      </section>

      <section aria-labelledby={`street-${street.id}-day`}>
        <div className="flex items-baseline justify-between">
          <h3 id={`street-${street.id}-day`} className="text-xs font-medium text-fg-muted">
            {meta.label} through the day
          </h3>
          <span className="text-[11px] text-fg-subtle">Typical weekday</span>
        </div>
        <div className="mt-3">
          <HourlyBars values={values} hour={hour} onHour={onHourChange} metric={metric} />
        </div>
        <dl className="mt-4 grid grid-cols-2 gap-2 text-xs">
          <div className="rounded-xl bg-surface-2 px-3 py-2">
            <dt className="text-fg-muted">Best window</dt>
            <dd className="mt-0.5 font-num font-semibold text-fg">
              {hourLabel(best.start)}–{hourLabel(best.end)} <span className="font-normal" style={{ color: BAND_VAR[scoreBand(best.avg)].ink }}>· {best.avg}</span>
            </dd>
          </div>
          <div className="rounded-xl bg-surface-2 px-3 py-2">
            <dt className="text-fg-muted">Toughest</dt>
            <dd className="mt-0.5 font-num font-semibold text-fg">
              {hourLabel(worst.start)}–{hourLabel(worst.end)} <span className="font-normal" style={{ color: BAND_VAR[scoreBand(worst.avg)].ink }}>· {worst.avg}</span>
            </dd>
          </div>
        </dl>
      </section>

      <section aria-labelledby={`street-${street.id}-month`}>
        <h3 id={`street-${street.id}-month`} className="text-xs font-medium text-fg-muted">
          Last 30 days
        </h3>
        <dl className="mt-2 grid grid-cols-3 divide-x divide-line rounded-xl border border-line">
          <div className="px-3 py-2.5">
            <dt className="text-[11px] text-fg-muted">Rides</dt>
            <dd className="font-num text-base font-semibold">{formatInt(street.passes30d)}</dd>
          </div>
          <div className="px-3 py-2.5">
            <dt className="text-[11px] text-fg-muted">Overall</dt>
            <dd className="pt-0.5">
              <Delta value={street.trend} unit=" pts" suffix="" />
            </dd>
          </div>
          <div className="px-3 py-2.5">
            <dt className="text-[11px] text-fg-muted">Potholes</dt>
            <dd className="font-num text-base font-semibold">{street.surface.potholes}</dd>
          </div>
        </dl>
      </section>

      <div className="flex gap-2">
        <Button asChild className="flex-1">
          <Link href={`/app/routes?via=${street.id}`}>
            <Route /> Route via this street
          </Link>
        </Button>
        <Button variant="secondary" size="icon" onClick={copyLink} aria-label={copied ? "Link copied" : "Copy link to this street"}>
          {copied ? <Check /> : <Link2 />}
        </Button>
      </div>

      <p className="flex items-start gap-2 text-[11px] leading-4 text-fg-subtle">
        <ShieldCheck className="mt-px size-3.5 shrink-0" aria-hidden />
        Anonymised and aggregated from {pluralize(street.passes30d, "ride")}. Trip starts and ends are trimmed before anything leaves your phone.
      </p>
    </article>
  );
}

// ------------------------------------------------------------------ city overview

function pickPerName(streets: StreetSegment[], metric: MapMetric, hour: number, pick: "best" | "worst") {
  const byName = new Map<string, { s: StreetSegment; score: number }>();
  for (const s of streets) {
    const score = scoreAt(s, metric, hour);
    const cur = byName.get(s.name);
    const better = !cur || (pick === "best" ? score > cur.score || (score === cur.score && s.passes30d > cur.s.passes30d) : score < cur.score);
    if (better) byName.set(s.name, { s, score });
  }
  return [...byName.values()].sort((a, b) => (pick === "best" ? b.score - a.score : a.score - b.score));
}

function StreetRow({ s, score, metric, rank, onPick }: { s: StreetSegment; score: number; metric: MapMetric; rank?: number; onPick: (id: string) => void }) {
  const span = streetSpan(s);
  return (
    <li>
      <button type="button" onClick={() => onPick(s.id)} className="flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left transition-colors hover:bg-surface-2">
        {rank ? <span className="w-4 shrink-0 text-center font-mono text-[11px] text-fg-subtle">{rank}</span> : null}
        <span className="min-w-0 flex-1">
          <span className="block truncate text-sm font-medium text-fg">{s.name}</span>
          <span className="block truncate text-xs text-fg-muted">{span ? `${span} · ${s.district}` : s.district}</span>
        </span>
        <ScoreBadge metric={metric} score={score} size="sm" showIcon={false} />
      </button>
    </li>
  );
}

export function CityAtHour({
  streets,
  metric,
  hour,
  query,
  onQueryChange,
  onPick,
  hideSummary,
}: {
  streets: StreetSegment[];
  metric: MapMetric;
  hour: number;
  query: string;
  onQueryChange: (q: string) => void;
  onPick: (id: string) => void;
  hideSummary?: boolean;
}) {
  const shares = useMemo(() => bandShares(streets, metric, hour), [streets, metric, hour]);
  const best = useMemo(() => pickPerName(streets, metric, hour, "best").slice(0, 5), [streets, metric, hour]);
  const worst = useMemo(() => pickPerName(streets, metric, hour, "worst").filter((x) => x.score < 70).slice(0, 5), [streets, metric, hour]);
  const results = useMemo(() => {
    const q = searchable(query.trim());
    if (!q) return [];
    const byName = new Map<string, StreetSegment[]>();
    for (const s of streets) {
      if (!searchable(`${s.name} ${s.from ?? ""} ${s.to ?? ""}`).includes(q)) continue;
      byName.set(s.name, [...(byName.get(s.name) ?? []), s]);
    }
    return [...byName.entries()]
      .map(([name, list]) => ({ name, list, top: list.reduce((a, b) => (b.passes30d > a.passes30d ? b : a)) }))
      .sort((a, b) => Number(!searchable(a.name).includes(q)) - Number(!searchable(b.name).includes(q)) || b.top.passes30d - a.top.passes30d)
      .slice(0, 6);
  }, [streets, query]);
  const sup = SUPERLATIVE[metric];
  const meta = DIMENSIONS[metric];

  return (
    <div className="space-y-6">
      {!hideSummary ? (
        <section aria-labelledby="city-now">
          <p className="label-mono text-[10px] text-fg-subtle">Barcelona · typical weekday</p>
          <h2 id="city-now" className="mt-1.5 font-display text-xl leading-snug font-semibold tracking-tight text-fg">
            At {hourLabel(hour)}, <span className="font-num">{shares.pct.good}%</span> of mapped streets {sup.goodPhrase}.
          </h2>
          <ShareBar shares={shares} className="mt-4" />
          <ul className="mt-3 grid grid-cols-3 gap-2 text-xs" aria-label={`${meta.label} score distribution at ${hourLabel(hour)}`}>
            {(["good", "mid", "bad"] as const).map((b) => (
              <li key={b}>
                <span className="flex items-center gap-1.5 text-fg-muted">
                  <span className="h-1.5 w-3 rounded-full" style={{ background: BAND_VAR[b].fill }} aria-hidden />
                  {meta.bands[b]}
                </span>
                <span className="mt-0.5 block font-num text-sm font-semibold text-fg">
                  {shares.pct[b]}% <span className="text-xs font-normal text-fg-subtle">· {formatKm(shares.km[b] * 1000, 0)}</span>
                </span>
              </li>
            ))}
          </ul>
        </section>
      ) : null}

      <section aria-label="Find a street">
        <div className="relative">
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-subtle" aria-hidden />
          <label htmlFor="street-search" className="sr-only">
            Find a street
          </label>
          <input
            id="street-search"
            type="search"
            value={query}
            onChange={(e) => onQueryChange(e.target.value)}
            placeholder="Find a street…"
            autoComplete="off"
            className="h-10 w-full rounded-xl border border-line bg-surface pr-3 pl-9 text-sm text-fg placeholder:text-fg-subtle focus-visible:border-signal/50 focus-visible:ring-4 focus-visible:ring-signal/15 focus-visible:outline-none"
          />
        </div>
        {query.trim() ? (
          results.length ? (
            <ul className="mt-2 space-y-0.5" aria-label="Matching streets">
              {results.map((r) => (
                <StreetRow key={r.name} s={r.top} score={scoreAt(r.top, metric, hour)} metric={metric} onPick={onPick} />
              ))}
            </ul>
          ) : (
            <p className="mt-3 px-2 text-sm text-fg-muted" role="status">
              No mapped street matches “{query.trim()}”. UMI scores a street once 5 riders have passed.
            </p>
          )
        ) : null}
      </section>

      {!query.trim() ? (
        <>
          <section aria-labelledby="city-best">
            <h3 id="city-best" className="flex items-center gap-2 px-2 text-xs font-medium text-fg-muted">
              <span className="size-1.5 rounded-full bg-good-fill" aria-hidden />
              {sup.best}
            </h3>
            <ol className="mt-1.5 space-y-0.5">
              {best.map((x, i) => (
                <StreetRow key={x.s.id} s={x.s} score={x.score} metric={metric} rank={i + 1} onPick={onPick} />
              ))}
            </ol>
          </section>
          <section aria-labelledby="city-worst">
            <h3 id="city-worst" className="flex items-center gap-2 px-2 text-xs font-medium text-fg-muted">
              <span className="size-1.5 rounded-full bg-bad-fill" aria-hidden />
              {sup.worst} at {hourLabel(hour)}
            </h3>
            {worst.length ? (
              <ol className="mt-1.5 space-y-0.5">
                {worst.map((x, i) => (
                  <StreetRow key={x.s.id} s={x.s} score={x.score} metric={metric} rank={i + 1} onPick={onPick} />
                ))}
              </ol>
            ) : (
              <p className="mt-2 px-2 text-sm text-fg-muted">Every mapped street scores 70 or more at this hour.</p>
            )}
          </section>
        </>
      ) : null}

      <p className="px-2 text-[11px] leading-4 text-fg-subtle">
        {formatInt(streets.length)} segments · {formatKm(shares.totalKm * 1000, 0)} scored by UMI riders over the last 30 days. Select a street on the map for its 24-hour profile.
      </p>
    </div>
  );
}
