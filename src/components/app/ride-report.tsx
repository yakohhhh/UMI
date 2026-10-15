"use client";

import { ArrowLeft, Bike, Download, Footprints, Hand, MessageCircle, MountainSnow, Share2, Thermometer, Timer, Zap } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { TimelineChart, type TimelinePoint, type TimelineSeries } from "@/components/charts/timeline-chart";
import { EmptyState, ErrorState } from "@/components/data/states";
import { StatTile } from "@/components/data/stat-tile";
import { ScoreDot } from "@/components/score/score-badge";
import { ScoreGauge } from "@/components/score/score-gauge";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { getActivity, getAthlete } from "@/lib/api";
import { formatActivityDate, formatDuration, formatKm, formatPace, signed } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";
import { mockNow } from "@/lib/mock";
import { bandLabel, scoreBand, BAND_VAR } from "@/lib/score";
import type { ActivityDetail } from "@/lib/types";
import { cn } from "@/lib/utils";
import { EVENT_META } from "./ride-events";

const RideMap = dynamic(() => import("./ride-map"), {
  ssr: false,
  loading: () => <Skeleton className="size-full rounded-none" />,
});

const SERIES: TimelineSeries[] = [
  { key: "speed", label: "Speed", unit: "km/h", color: "#8cb8ff", digits: 1, domain: [0, "auto"] },
  { key: "vib", label: "Vibration", unit: "m/s²", color: "#3d9bff", digits: 2, domain: [0, "auto"], references: [{ y: 1.5, label: "BUMPY 1.5" }] },
  {
    key: "pm25",
    label: "PM2.5",
    unit: "µg/m³",
    color: "#f5c542",
    digits: 1,
    domain: [0, "auto"],
    references: [
      { y: 10, label: "EU 2030 · 10", color: "#3d9bff", below: true },
      { y: 15, label: "WHO 24 h · 15", color: "#f5c542" },
    ],
  },
  { key: "db", label: "Noise", unit: "dB(A)", color: "#ff7a47", digits: 0, domain: [45, "auto"], references: [{ y: 53, label: "WHO 53", color: "#3d9bff" }] },
];

const COMMENTS = [
  { name: "Núria Vila", text: "That Verdaguer junction again 😅 I brake there every morning too.", time: "07:58" },
  { name: "Marc Ferrer", text: "The 8:05 spike lines up with the 7 bus at the Glòries lights. Try Consell de Cent tomorrow?", time: "08:20" },
  { name: "Jordi Soler", text: "Nice comfort score for Diagonal at rush hour.", time: "09:02" },
];

function ReportSkeleton() {
  return (
    <div className="mx-auto max-w-[1180px] space-y-6 px-4 py-6 sm:px-6 lg:py-8" aria-busy="true" aria-label="Loading ride report">
      <Skeleton className="h-5 w-24" />
      <Skeleton className="h-10 w-80" />
      <Skeleton className="h-20 w-full" />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Skeleton className="h-[440px]" />
        <Skeleton className="h-[440px]" />
      </div>
    </div>
  );
}

export function RideReport() {
  const { id } = useParams<{ id: string }>();
  const activity = useApi(() => getActivity(id), [id]);
  const athleteId = activity.data?.athleteId;
  const athlete = useApi(() => (athleteId ? getAthlete(athleteId) : Promise.resolve(null)), [athleteId]);
  const [active, setActive] = useState<number | null>(null);
  const [selectedEvent, setSelectedEvent] = useState<number | null>(null);
  const [kudoed, setKudoed] = useState(false);

  if (activity.error) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <ErrorState error={activity.error} onRetry={activity.retry} />
      </div>
    );
  }
  if (activity.loading && !activity.data) return <ReportSkeleton />;
  if (!activity.data) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-10">
        <EmptyState
          title="This ride doesn't exist (anymore)"
          body="It may have been deleted or made private by its owner."
          action={
            <Button asChild variant="secondary" size="sm">
              <Link href="/app">Back to the feed</Link>
            </Button>
          }
        />
      </div>
    );
  }
  return <Report a={activity.data} athleteName={athlete.data?.name ?? "Laia Serra"} active={active} setActive={setActive} selectedEvent={selectedEvent} setSelectedEvent={setSelectedEvent} kudoed={kudoed} setKudoed={setKudoed} />;
}

function Report({
  a,
  athleteName,
  active,
  setActive,
  selectedEvent,
  setSelectedEvent,
  kudoed,
  setKudoed,
}: {
  a: ActivityDetail;
  athleteName: string;
  active: number | null;
  setActive: (i: number | null) => void;
  selectedEvent: number | null;
  setSelectedEvent: (i: number | null) => void;
  kudoed: boolean;
  setKudoed: (fn: (k: boolean) => boolean) => void;
}) {
  const data: TimelinePoint[] = useMemo(() => a.samples.map(([t, d, speed, vib, pm25, db]) => ({ t: t / 60, d: d / 1000, speed, vib, pm25, db })), [a.samples]);
  const series = useMemo(
    () =>
      SERIES.map((s) => ({
        ...s,
        events: a.events
          .filter((e) => (s.key === "speed" && e.type === "hard_brake") || (s.key === "vib" && e.type === "pothole") || (s.key === "pm25" && e.type === "pm_spike") || (s.key === "db" && e.type === "noise_peak"))
          .map((e) => ({ t: a.samples[e.sampleIndex][0] / 60, label: e.time })),
      })),
    [a],
  );
  const Icon = a.type === "ride" ? Bike : Footprints;

  return (
    <div className="mx-auto max-w-[1180px] space-y-6 px-4 py-6 sm:px-6 lg:py-8">
      <Link href="/app" className="inline-flex items-center gap-1.5 text-sm text-fg-muted hover:text-fg">
        <ArrowLeft className="size-4" /> Feed
      </Link>

      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div className="flex items-start gap-3">
          <Avatar name={athleteName} size={44} />
          <div>
            <p className="flex items-center gap-1.5 text-sm text-fg-muted">
              <Icon className="size-4" /> {athleteName} · <time dateTime={a.startedAt}>{formatActivityDate(a.startedAt, mockNow())}</time> · {a.place}
            </p>
            <h1 className="mt-1 font-display text-3xl font-semibold tracking-tight sm:text-4xl">{a.title}</h1>
            {a.description ? <p className="mt-2 max-w-2xl text-fg-muted">{a.description}</p> : null}
          </div>
        </div>
        <div className="flex gap-2">
          <Button variant={kudoed ? "primary" : "secondary"} size="sm" onClick={() => setKudoed((k) => !k)} aria-pressed={kudoed}>
            <Hand /> {a.kudos + (kudoed ? 1 : 0)} kudos
          </Button>
          <Button variant="secondary" size="sm" asChild>
            <a href="#comments">
              <MessageCircle /> {a.comments}
            </a>
          </Button>
          <Button variant="secondary" size="icon-sm" aria-label="Export GPX">
            <Download />
          </Button>
          <Button variant="secondary" size="icon-sm" aria-label="Share">
            <Share2 />
          </Button>
        </div>
      </header>

      <Card>
        <CardContent className="grid grid-cols-2 gap-x-6 gap-y-4 pt-5 sm:grid-cols-3 lg:grid-cols-6">
          <StatTile label="Distance" value={(a.distanceM / 1000).toFixed(2)} unit="km" />
          <StatTile label="Moving time" value={formatDuration(a.movingTimeS, "clock")} />
          <StatTile label={a.type === "run" ? "Pace" : "Avg speed"} value={a.type === "run" ? formatPace(a.distanceM, a.movingTimeS).replace(" /km", "") : a.avgSpeedKmh.toFixed(1)} unit={a.type === "run" ? "/km" : "km/h"} />
          <StatTile label="Max speed" value={a.maxSpeedKmh.toFixed(1)} unit="km/h" icon={<Zap />} />
          <StatTile label="Elevation" value={a.elevationGainM} unit="m" icon={<MountainSnow />} />
          <StatTile label="Weather" value={`${a.weather.tempC}°`} sub={a.weather.condition} icon={<Thermometer />} />
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <Card className="overflow-hidden">
          <div className="h-[380px] sm:h-[460px]">
            <RideMap activity={a} activeIndex={active} selectedEvent={selectedEvent} onSelectEvent={setSelectedEvent} />
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line px-4 py-3 text-xs text-fg-muted">
            <span>Trace coloured by street score:</span>
            {(["good", "mid", "bad"] as const).map((b) => (
              <span key={b} className="inline-flex items-center gap-1.5">
                <span className="h-1.5 w-4 rounded-full" style={{ background: BAND_VAR[b].fill }} />
                {b === "good" ? "Calm 70+" : b === "mid" ? "Mixed 45–69" : "Stressful <45"}
              </span>
            ))}
          </div>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Ride scores</CardTitle>
            <span className="text-xs text-fg-muted">out of 100</span>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-x-2 gap-y-6 pt-6">
            <ScoreGauge metric="comfort" score={a.scores.comfort} size={118} />
            <ScoreGauge metric="safety" score={a.scores.safety} size={118} />
            <ScoreGauge metric="air" score={a.scores.air} size={118} />
            <ScoreGauge metric="noise" score={a.scores.noise} size={118} />
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Along the ride</CardTitle>
            <p className="mt-0.5 text-xs text-fg-muted">Hover the charts: the orange dot follows on the map.</p>
          </div>
          <Timer className="size-4 text-fg-subtle" aria-hidden />
        </CardHeader>
        <CardContent className="space-y-4">
          {series.map((s, i) => (
            <TimelineChart key={s.key} data={data} series={s} syncId={`ride-${a.id}`} activeIndex={active} onHover={setActive} showAxis={i === series.length - 1} height={i === series.length - 1 ? 128 : 96} />
          ))}
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
        <Card>
          <CardHeader>
            <div>
              <CardTitle>Street segments</CardTitle>
              <p className="mt-0.5 text-xs text-fg-muted">Your score on each segment vs the street&apos;s 30-day average</p>
            </div>
          </CardHeader>
          <CardContent className="pt-3">
            <ul className="divide-y divide-line">
              {a.segments.map((s, i) => {
                const diff = s.score - s.streetAverage;
                return (
                  <li key={`${s.segmentId}-${i}`} className="grid grid-cols-[1fr_auto] items-center gap-3 py-3 sm:grid-cols-[1fr_180px_auto]">
                    <div className="min-w-0">
                      <p className="flex items-center gap-2 truncate text-sm font-medium">
                        <ScoreDot score={s.score} />
                        <Link href={`/app/map?street=${s.segmentId}`} className="truncate hover:text-accent-ink hover:underline hover:underline-offset-2">
                          {s.name}
                        </Link>
                      </p>
                      <p className="truncate text-xs text-fg-muted">
                        {[s.from, s.to].filter(Boolean).join(" → ") || "Segment"} · {formatKm(s.distanceM, 2)}
                        {s.bikeLane ? " · bike lane" : ""}
                      </p>
                    </div>
                    <div className="hidden sm:block" aria-hidden>
                      <div className="relative h-2 rounded-full bg-surface-2">
                        <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${s.score}%`, background: BAND_VAR[scoreBand(s.score)].fill }} />
                        <div className="absolute -top-1 h-4 w-0.5 rounded bg-fg" style={{ left: `${s.streetAverage}%` }} title="Street average" />
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-num text-base font-semibold" aria-label={`Your score ${s.score}, ${bandLabel(s.score)}`}>
                        {s.score}
                      </p>
                      <p className={cn("text-[11px]", diff >= 0 ? "text-good" : "text-bad")}>
                        {signed(diff)} vs avg {s.streetAverage}
                      </p>
                    </div>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>

        <div className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Moments</CardTitle>
              <Badge variant="neutral" size="sm">
                {a.events.length}
              </Badge>
            </CardHeader>
            <CardContent className="pt-3">
              {a.events.length ? (
                <ul className="space-y-2">
                  {a.events.map((e, i) => {
                    const meta = EVENT_META[e.type];
                    return (
                      <li key={`${e.type}-${i}`}>
                        <button
                          type="button"
                          onClick={() => setSelectedEvent(selectedEvent === i ? null : i)}
                          aria-pressed={selectedEvent === i}
                          className={cn(
                            "flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-left transition-colors",
                            selectedEvent === i ? "border-signal/50 bg-signal/8" : "border-line hover:bg-surface-2",
                          )}
                        >
                          <span className="flex size-8 shrink-0 items-center justify-center rounded-full" style={{ background: `color-mix(in srgb, ${meta.color} 20%, transparent)` }}>
                            <meta.icon className="size-4" style={{ color: meta.color }} />
                          </span>
                          <span className="min-w-0 flex-1">
                            <span className="block text-sm font-medium">
                              {meta.label} <span className="font-mono text-xs text-fg-muted">{e.time}</span>
                            </span>
                            <span className="block truncate text-xs text-fg-muted">
                              {e.value} {meta.unit} · {e.street ?? meta.explain}
                            </span>
                          </span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              ) : (
                <p className="text-sm text-fg-muted">A smooth one: no hard brakes, impacts or pollution spikes recorded.</p>
              )}
            </CardContent>
          </Card>

          <Card id="comments">
            <CardHeader>
              <CardTitle>Comments</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 pt-3">
              {COMMENTS.slice(0, Math.max(1, Math.min(3, a.comments))).map((c) => (
                <div key={c.name} className="flex gap-3">
                  <Avatar name={c.name} size={30} />
                  <div className="min-w-0">
                    <p className="text-xs">
                      <span className="font-semibold text-fg">{c.name}</span> <span className="text-fg-subtle">{c.time}</span>
                    </p>
                    <p className="text-sm text-fg-muted">{c.text}</p>
                  </div>
                </div>
              ))}
              <form className="flex gap-2 pt-1" onSubmit={(e) => e.preventDefault()}>
                <label htmlFor="comment" className="sr-only">
                  Add a comment
                </label>
                <input id="comment" placeholder="Add a comment…" className="h-9 flex-1 rounded-xl border border-line bg-surface-2 px-3 text-sm placeholder:text-fg-subtle focus-visible:border-signal/50 focus-visible:outline-none" />
                <Button size="sm" type="submit">
                  Post
                </Button>
              </form>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
