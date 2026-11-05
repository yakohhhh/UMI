"use client";

import {
  ArrowLeft,
  Bike,
  CircleCheckBig,
  Download,
  Flag,
  Footprints,
  Gauge,
  Hand,
  Lock,
  MessageCircle,
  MessageCircleQuestionMark,
  MountainSnow,
  Share2,
  Thermometer,
  Timer,
  Users,
  Wrench,
  Zap,
  type LucideIcon,
} from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
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
import { answerBrakeCause, answerFlagKind, CURRENT_ATHLETE_ID, getActivity, getAthlete, getBrakeHotspots } from "@/lib/api";
import { formatActivityDate, formatDuration, formatKm, formatPace, signed } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";
import { mockNow } from "@/lib/mock";
import { CAUSE_BUCKET, CITY_MIN_RIDERS, HAZARD_LIFETIME, MAP_MIN_RIDERS, momentsToCheck } from "@/lib/reports";
import { bandLabel, scoreBand, BAND_VAR } from "@/lib/score";
import type { ActivityDetail, ActivitySummary, BrakeCause, BrakeHotspot, CauseBucket, FlagStatus, HazardKind, RideEvent, RideFlag } from "@/lib/types";
import { cn } from "@/lib/utils";
import { eventSummary } from "./activity-card";
import { BUCKET_META, CAUSE_META, EVENT_META, flagReach, FLAG_SOURCE_LABEL, FLAG_STATUS_META, HAZARD_META } from "./ride-events";

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

const BUCKET_ICON: Record<CauseBucket, LucideIcon> = { infrastructure: Wrench, behaviour: Users, personal: Lock };

/** Short names for a junction's cause mix. */
const CAUSE_SHORT: Record<BrakeCause | "other", string> = {
  vehicle: "vehicle",
  pedestrian: "pedestrian",
  animal: "animal",
  car_door: "car door",
  lane_blocked: "blocked lane",
  junction: "junction",
  surface: "surface",
  roadworks: "roadworks",
  just_me: "just me",
  other: "other",
};

const CAUSES = Object.keys(CAUSE_META) as BrakeCause[];
const KINDS = Object.keys(HAZARD_META) as HazardKind[];

type Moment = { kind: "event"; item: RideEvent } | { kind: "flag"; item: RideFlag };

const pct = (share: number) => `${Math.round(share * 100)}%`;
const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

function without<T>(r: Record<string, T>, id: string) {
  const next = { ...r };
  delete next[id];
  return next;
}

/** Optimistic answers keyed by event or flag id: shown at once, reverted with a short note if the save fails. */
function useAnswers<V extends string>(save: (id: string, value: V) => Promise<unknown>) {
  const [values, setValues] = useState<Record<string, V>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const latest = useRef<Record<string, number>>({});
  const answer = (id: string, value: V) => {
    const prev = values[id];
    const n = (latest.current[id] ?? 0) + 1;
    latest.current[id] = n;
    setValues((v) => ({ ...v, [id]: value }));
    setErrors((e) => without(e, id));
    save(id, value).catch(() => {
      // a newer answer went out since: never revert over it
      if (latest.current[id] !== n) return;
      setValues((v) => (prev === undefined ? without(v, id) : { ...v, [id]: prev }));
      setErrors((e) => ({ ...e, [id]: "Couldn't save that. Try again in a moment." }));
    });
  };
  return { values, errors, answer };
}

/** A callback ref that focuses the next element it gets after `arm()`: keyboard users keep their place when a question opens or closes. */
function useHandOff() {
  const armed = useRef(false);
  return {
    arm: () => {
      armed.current = true;
    },
    ref: (el: HTMLElement | null) => {
      if (el && armed.current) {
        armed.current = false;
        el.focus();
      }
    },
  };
}

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
  const hotspots = useApi(() => getBrakeHotspots(), []);

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
  // useApi keeps the previous athlete while refetching: only trust a name that belongs to this ride
  const name = athlete.data && athlete.data.id === athleteId ? athlete.data.name : athleteId === CURRENT_ATHLETE_ID ? "Laia Serra" : "Rider";
  return <Report key={activity.data.id} a={activity.data} athleteName={name} hotspots={hotspots.data ?? []} />;
}

function Report({ a: loaded, athleteName, hotspots }: { a: ActivityDetail; athleteName: string; hotspots: BrakeHotspot[] }) {
  const [active, setActive] = useState<number | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [kudoed, setKudoed] = useState(false);
  const own = loaded.athleteId === CURRENT_ATHLETE_ID;
  const causes = useAnswers<BrakeCause>((eventId, cause) => answerBrakeCause(loaded.id, eventId, cause));
  const kinds = useAnswers<HazardKind>((flagId, kind) => answerFlagKind(loaded.id, flagId, kind));

  // the ride as the rider sees it right now, answers included before the server confirms them
  const a = useMemo<ActivityDetail>(
    () => ({
      ...loaded,
      events: loaded.events.map((e) => (e.id in causes.values ? { ...e, cause: causes.values[e.id] } : e)),
      flags: loaded.flags.map((f) => (f.id in kinds.values ? { ...f, kind: kinds.values[f.id] } : f)),
    }),
    [loaded, causes.values, kinds.values],
  );

  const data: TimelinePoint[] = useMemo(() => loaded.samples.map(([t, d, speed, vib, pm25, db]) => ({ t: t / 60, d: d / 1000, speed, vib, pm25, db })), [loaded.samples]);
  const series = useMemo(() => {
    const minuteAt = (i: number) => loaded.samples[Math.min(i, loaded.samples.length - 1)][0] / 60;
    return SERIES.map((s) => ({
      ...s,
      events: [
        ...loaded.events
          .filter((e) => (s.key === "speed" && e.type === "hard_brake") || (s.key === "vib" && e.type === "pothole") || (s.key === "pm25" && e.type === "pm_spike") || (s.key === "db" && e.type === "noise_peak"))
          .map((e) => ({ t: minuteAt(e.sampleIndex), label: e.time })),
        ...(s.key === "speed" ? loaded.flags.map((f) => ({ t: minuteAt(f.sampleIndex), label: f.time })) : []),
      ],
    }));
  }, [loaded]);

  const moments = useMemo<Moment[]>(
    () => [...a.events.map((item) => ({ kind: "event" as const, item })), ...a.flags.map((item) => ({ kind: "flag" as const, item }))].sort((x, y) => x.item.sampleIndex - y.item.sampleIndex),
    [a],
  );
  const summary = eventSummary(a.events, a.flags);
  const toggle = (id: string) => setSelectedId((cur) => (cur === id ? null : id));
  const hotspotFor = (e: RideEvent) => {
    const street = e.street;
    if (e.type !== "hard_brake" || !street) return null;
    return hotspots.find((h) => h.label.startsWith(street)) ?? null;
  };
  const Icon = a.type === "ride" ? Bike : Footprints;

  // the feed's "moments to check" nudge links here; the card only exists once the ride has loaded
  useEffect(() => {
    if (window.location.hash === "#moments") document.getElementById("moments")?.scrollIntoView({ block: "start" });
  }, []);

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
            <RideMap activity={a} activeIndex={active} selectedId={selectedId} onSelect={setSelectedId} />
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-line px-4 py-3 text-xs text-fg-muted">
            <span>Trace coloured by street score:</span>
            {(["good", "mid", "bad"] as const).map((b) => (
              <span key={b} className="inline-flex items-center gap-1.5">
                <span className="h-1.5 w-4 rounded-full" style={{ background: BAND_VAR[b].fill }} />
                {b === "good" ? "Calm 70+" : b === "mid" ? "Mixed 45–69" : "Stressful <45"}
              </span>
            ))}
            {a.flags.length ? (
              <span className="inline-flex items-center gap-3 sm:ml-auto">
                <span className="inline-flex items-center gap-1.5">
                  <span className="size-3 rounded-full border-2 border-fg-subtle bg-surface" aria-hidden />
                  Sensors
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span className="size-3 rounded-[4px] border-2 border-signal bg-surface" aria-hidden />
                  {own ? "Your flags" : "Flags"}
                </span>
              </span>
            ) : null}
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
            <p className="mt-0.5 text-xs text-fg-muted">Hover the charts: the orange dot follows on the map.{a.flags.length ? " Flags sit on the speed line." : ""}</p>
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
          <Card id="moments" className="scroll-mt-24" aria-labelledby="moments-title">
            <CardHeader>
              <div className="min-w-0">
                <CardTitle id="moments-title">Moments</CardTitle>
                {summary ? <p className="mt-0.5 text-xs text-fg-muted">{summary}</p> : null}
              </div>
              <Badge variant="neutral" size="sm">
                {moments.length}
              </Badge>
            </CardHeader>
            <CardContent className="pt-3">
              {own ? <CheckCallout a={a} /> : null}
              {moments.length ? (
                <ul className="space-y-2">
                  {moments.map((m) =>
                    m.kind === "event" ? (
                      <EventMoment
                        key={m.item.id}
                        e={m.item}
                        own={own}
                        hotspot={hotspotFor(m.item)}
                        selected={selectedId === m.item.id}
                        onToggle={() => toggle(m.item.id)}
                        onAnswer={(cause) => causes.answer(m.item.id, cause)}
                        error={causes.errors[m.item.id]}
                      />
                    ) : (
                      <FlagMoment
                        key={m.item.id}
                        f={m.item}
                        own={own}
                        answeredHere={m.item.id in kinds.values}
                        selected={selectedId === m.item.id}
                        onToggle={() => toggle(m.item.id)}
                        onAnswer={(kind) => kinds.answer(m.item.id, kind)}
                        error={kinds.errors[m.item.id]}
                      />
                    ),
                  )}
                </ul>
              ) : (
                <p className="text-sm text-fg-muted">Smooth as fresh asphalt: no hard brakes, impacts or spikes, and nothing flagged.</p>
              )}
              {!a.events.length && a.flags.length ? (
                <p className="mt-3 text-xs text-fg-subtle">The sensors stayed quiet: no hard brakes, impacts or spikes. Just what {own ? "you" : athleteName.split(" ")[0]} flagged.</p>
              ) : null}
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

/** Top of the Moments card on the rider's own rides: what is left to answer, or a thank-you once it's done. */
function CheckCallout({ a }: { a: Pick<ActivitySummary, "events" | "flags"> }) {
  const n = momentsToCheck(a);
  const brakesLeft = a.events.some((e) => e.ask && !e.cause);
  const hadQuestions = a.events.some((e) => e.ask) || a.flags.some((f) => f.source === "press");
  if (!n && !hadQuestions) return null;
  return (
    <div aria-live="polite" className="mb-3">
      {n ? (
        <div className="rounded-xl border border-signal/25 bg-signal/8 px-3 py-2.5">
          <p className="flex items-center gap-2 text-sm font-medium text-fg">
            <MessageCircleQuestionMark className="size-4 shrink-0 text-accent-ink" aria-hidden />
            {plural(n, "moment", "moments")} to check · under 10 seconds
          </p>
          <p className="mt-0.5 pl-6 text-xs text-fg-muted">
            Asked after the ride, never while you ride. {brakesLeft ? "Skip any: an unanswered brake still counts, at half weight." : "One tap each, or skip."}
          </p>
        </div>
      ) : (
        <p className="flex items-start gap-2 rounded-xl bg-surface-2 px-3 py-2.5 text-xs text-fg-muted">
          <CircleCheckBig className="mt-px size-4 shrink-0 text-good" aria-hidden />
          <span>
            <span className="font-medium text-fg">All checked, thanks.</span> Answering earns nothing by itself, so “just me” counts like any other answer. Credit comes when other riders verify your flags or the city fixes them.
          </span>
        </p>
      )}
    </div>
  );
}

/** One row of the Moments list: the header shows it on the map, the body holds context and the after-ride question. */
function MomentShell({
  selected,
  onToggle,
  icon,
  title,
  sub,
  children,
}: {
  selected: boolean;
  onToggle: () => void;
  icon: ReactNode;
  title: ReactNode;
  sub: ReactNode;
  children?: ReactNode;
}) {
  return (
    <li className={cn("rounded-xl border transition-colors", selected ? "border-signal/50 bg-signal/8" : "border-line")}>
      <button type="button" onClick={onToggle} aria-pressed={selected} className={cn("flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left transition-colors", !selected && "hover:bg-surface-2")}>
        {icon}
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium">{title}</span>
          <span className="line-clamp-2 block text-xs text-fg-muted">{sub}</span>
          <span className="sr-only">, show on the map</span>
        </span>
      </button>
      {children ? <div className="space-y-2 pr-3 pb-3 pl-3 sm:pl-14">{children}</div> : null}
    </li>
  );
}

function EventMoment({
  e,
  own,
  hotspot,
  selected,
  onToggle,
  onAnswer,
  error,
}: {
  e: RideEvent;
  own: boolean;
  hotspot: BrakeHotspot | null;
  selected: boolean;
  onToggle: () => void;
  onAnswer: (cause: BrakeCause) => void;
  error?: string;
}) {
  const meta = EVENT_META[e.type];
  const brake = e.type === "hard_brake";
  const hasBody = brake && (hotspot || own || e.cause);
  return (
    <MomentShell
      selected={selected}
      onToggle={onToggle}
      icon={
        <span className="flex size-8 shrink-0 items-center justify-center rounded-full" style={{ background: `color-mix(in srgb, ${meta.color} 20%, transparent)` }}>
          <meta.icon className="size-4" style={{ color: meta.color }} aria-hidden />
        </span>
      }
      title={
        <>
          {meta.label} <span className="font-mono text-xs text-fg-muted">{e.time}</span>
        </>
      }
      sub={
        <>
          {e.value} {meta.unit} · {e.street ?? meta.explain}
        </>
      }
    >
      {hasBody ? (
        <>
          {hotspot ? <HotspotContext h={hotspot} /> : null}
          {own ? <CauseQuestion e={e} onAnswer={onAnswer} error={error} /> : e.cause ? <CauseReadOnly cause={e.cause} /> : null}
        </>
      ) : null}
    </MomentShell>
  );
}

/** How this brake compares with everyone else's at the same junction (5+ riders, rounded to 10 %, no "just me"). */
function HotspotContext({ h }: { h: BrakeHotspot }) {
  const named = (h.causes ?? []).filter((c): c is { cause: BrakeCause; share: number } => c.cause !== "other");
  const top = named.reduce<(typeof named)[number] | null>((best, c) => (!best || c.share > best.share ? c : best), null);
  return (
    <div className="space-y-0.5">
      <p className="flex items-start gap-1.5 text-xs text-fg-muted">
        <Users className="mt-0.5 size-3.5 shrink-0" aria-hidden />
        <span>
          <span className="font-num font-medium text-fg">{h.hardBrakesWeek}</span> hard brakes here this week
          {top ? ` · mostly ${CAUSE_META[top.cause].label.toLowerCase()} (${pct(top.share)})` : ""}
        </span>
      </p>
      {h.causes?.length ? (
        <p className="pl-5 text-[11px] text-fg-subtle">
          Why{h.answeredBy ? `, from ${h.answeredBy} riders who said` : ""}: {h.causes.map((c) => `${CAUSE_SHORT[c.cause]} ${pct(c.share)}`).join(" · ")}
        </p>
      ) : null}
    </div>
  );
}

/** "Why did you brake?" on the rider's own ride: open by default when the app asked, one tap, changeable, skippable. */
function CauseQuestion({ e, onAnswer, error }: { e: RideEvent; onAnswer: (cause: BrakeCause) => void; error?: string }) {
  const [mode, setMode] = useState<"auto" | "open" | "closed">("auto");
  const focus = useHandOff();
  const qid = useId();
  const cause = e.cause ?? null;
  const go = (next: "auto" | "open" | "closed") => {
    focus.arm();
    setMode(next);
  };
  const open = mode === "open" || (mode === "auto" && !cause && !!e.ask);
  const errorLine = error ? (
    <p role="alert" className="text-[11px] text-bad">
      {error}
    </p>
  ) : null;

  if (open) {
    return (
      <div ref={focus.ref} tabIndex={-1} role="group" aria-labelledby={qid} className="rounded-lg border border-line bg-surface-2/60 p-2.5">
        <p id={qid} className="text-xs font-medium text-fg">
          Why did you brake?
        </p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {CAUSES.map((c) => (
            <Chip
              key={c}
              icon={CAUSE_META[c].icon}
              label={CAUSE_META[c].label}
              pressed={cause === c}
              onClick={() => {
                go("auto");
                onAnswer(c);
              }}
            />
          ))}
        </div>
        <div className="mt-2 flex items-start justify-between gap-3">
          <p className="text-[11px] text-fg-subtle">Every answer counts the same, “just me” included.</p>
          <button type="button" onClick={() => go("closed")} className="-mx-2 -my-2 inline-flex min-h-8 shrink-0 items-center rounded px-2 text-[11px] font-medium text-fg-muted hover:text-fg">
            {cause ? "Keep it" : "Not now"}
          </button>
        </div>
        {errorLine ? <div className="mt-1.5">{errorLine}</div> : null}
      </div>
    );
  }

  if (cause) {
    const bucket = CAUSE_BUCKET[cause];
    const Cause = CAUSE_META[cause].icon;
    const Bucket = BUCKET_ICON[bucket];
    return (
      <div ref={focus.ref} tabIndex={-1} className="rounded-lg bg-surface-2/60 px-2.5 py-2">
        <div className="flex items-start gap-2">
          <Cause className="mt-0.5 size-3.5 shrink-0 text-fg" aria-hidden />
          <div className="min-w-0 flex-1">
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs font-medium text-fg">
              {CAUSE_META[cause].label}
              <Badge variant="outline" size="sm">
                <Bucket aria-hidden />
                {BUCKET_META[bucket].label}
              </Badge>
            </p>
            <p className="mt-0.5 text-[11px] text-fg-muted">{BUCKET_META[bucket].detail}</p>
          </div>
          <button type="button" onClick={() => go("open")} aria-label={`Change why you braked (now: ${CAUSE_META[cause].label})`} className="-mx-2 -my-2 inline-flex min-h-8 shrink-0 items-center rounded px-2 text-[11px] font-medium text-accent-ink hover:underline">
            Change
          </button>
        </div>
        {errorLine ? <div className="mt-1.5">{errorLine}</div> : null}
      </div>
    );
  }

  return (
    <div ref={focus.ref} tabIndex={-1} className="space-y-1">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-muted">
        <span>No reason yet · counts at half weight</span>
        <button type="button" onClick={() => go("open")} aria-expanded={false} className="-mx-2 -my-2 inline-flex min-h-8 items-center rounded px-2 font-medium text-accent-ink hover:underline">
          Why did you brake?
        </button>
      </p>
      {errorLine}
    </div>
  );
}

function CauseReadOnly({ cause }: { cause: BrakeCause }) {
  const Cause = CAUSE_META[cause].icon;
  const bucket = CAUSE_BUCKET[cause];
  return (
    <p className="flex items-center gap-1.5 text-xs text-fg-muted">
      <Cause className="size-3.5 shrink-0" aria-hidden />
      <span>
        Said why: <span className="font-medium text-fg">{CAUSE_META[cause].label}</span>
        {bucket !== "personal" ? ` · ${BUCKET_META[bucket].label}` : ""}
      </span>
    </p>
  );
}

function Chip({ icon: Icon, label, pressed, onClick }: { icon: LucideIcon; label: string; pressed: boolean; onClick: () => void }) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      onClick={onClick}
      className={cn(
        "inline-flex h-8 items-center gap-1.5 rounded-full border px-2.5 text-xs font-medium transition-colors",
        pressed ? "border-signal/50 bg-signal/12 text-accent-ink" : "border-line bg-surface text-fg-muted hover:border-line-strong hover:text-fg",
      )}
    >
      <Icon className="size-3.5 shrink-0" aria-hidden />
      {label}
    </button>
  );
}

function StatusChip({ status }: { status: FlagStatus }) {
  const meta = FLAG_STATUS_META[status];
  return (
    <Badge size="sm" variant={meta.tone === "good" ? "neutral" : meta.tone} className={cn(meta.tone === "good" && "border-good/25 bg-good/12 text-good")}>
      <meta.icon aria-hidden />
      {meta.label}
    </Badge>
  );
}

/** What happens next to the rider's own flag; fixed and gone flags speak through their proof instead. */
function flagNext(f: RideFlag) {
  const riders = f.confirmations + 1; // the confirmations are other riders, plus you
  const more = (min: number) => {
    const left = Math.max(1, min - riders);
    return left === 1 ? "One more rider" : `${left} more riders`;
  };
  if (f.status === "pending") return `${more(MAP_MIN_RIDERS)} and it shows on everyone's street map.`;
  if (f.status === "verified") return `On everyone's street map. ${more(CITY_MIN_RIDERS)} and it goes to the city.`;
  if (f.status === "sent_to_city") return "In City Insights and the city's IRIS queue, never with your name.";
  return null;
}

function FlagMoment({
  f,
  own,
  answeredHere,
  selected,
  onToggle,
  onAnswer,
  error,
}: {
  f: RideFlag;
  own: boolean;
  /** The kind was picked in this session, so it can still be changed. */
  answeredHere: boolean;
  selected: boolean;
  onToggle: () => void;
  onAnswer: (kind: HazardKind) => void;
  error?: string;
}) {
  const hazard = f.kind ? HAZARD_META[f.kind] : null;
  const KindIcon = hazard?.icon ?? Flag;
  const source = FLAG_SOURCE_LABEL[f.source];
  const next = own ? flagNext(f) : null;
  const live = own && f.kind && (f.status === "pending" || f.status === "verified") ? HAZARD_LIFETIME[f.kind] : null;

  return (
    <MomentShell
      selected={selected}
      onToggle={onToggle}
      icon={
        // a rounded square with a signal edge, like on the map: something the rider did, not something the sensors measured
        <span className={cn("flex size-8 shrink-0 items-center justify-center rounded-[10px] border border-signal/50", !hazard && "bg-signal/10")} style={hazard ? { background: `color-mix(in srgb, ${hazard.color} 20%, transparent)` } : undefined}>
          <KindIcon className={cn("size-4", !hazard && "text-accent-ink")} style={hazard ? { color: hazard.color } : undefined} aria-hidden />
        </span>
      }
      title={hazard ? hazard.label : "Flag · no word said"}
      sub={
        <>
          <source.icon className="mr-1 inline size-3 align-[-2px]" aria-hidden />
          {source.short} · {f.time}
          {f.street ? ` · ${f.street}` : ""}
        </>
      }
    >
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <StatusChip status={f.status} />
        <span className="text-xs text-fg-muted">{flagReach(f, own)}</span>
      </div>
      {f.proof ? (
        <p className="flex items-start gap-1.5 rounded-lg bg-surface-2/60 px-2.5 py-1.5 text-xs text-fg">
          <Gauge className="mt-0.5 size-3.5 shrink-0 text-fg-muted" aria-hidden />
          {f.proof}
        </p>
      ) : null}
      {next || live ? (
        <p className="text-[11px] text-fg-subtle">
          {next}
          {next && live ? " " : ""}
          {live ? `Stays live: ${live}.` : ""}
        </p>
      ) : null}
      {own && (!f.kind || answeredHere) ? <KindQuestion kind={f.kind} onAnswer={onAnswer} error={error} /> : null}
    </MomentShell>
  );
}

/** "What was it?" for a flag pressed without a keyword: the press already fixed where and when, this only adds what. */
function KindQuestion({ kind, onAnswer, error }: { kind: HazardKind | null; onAnswer: (kind: HazardKind) => void; error?: string }) {
  const [mode, setMode] = useState<"auto" | "open" | "closed">("auto");
  const focus = useHandOff();
  const qid = useId();
  const open = mode === "open" || (mode === "auto" && !kind);
  const go = (next: "auto" | "open" | "closed") => {
    focus.arm();
    setMode(next);
  };
  const errorLine = error ? (
    <p role="alert" className="text-[11px] text-bad">
      {error}
    </p>
  ) : null;

  if (open) {
    return (
      <div ref={focus.ref} tabIndex={-1} role="group" aria-labelledby={qid} className="rounded-lg border border-line bg-surface-2/60 p-2.5">
        <p id={qid} className="text-xs font-medium text-fg">
          What was it?
        </p>
        <div className="mt-2 flex flex-wrap gap-1.5">
          {KINDS.map((k) => (
            <Chip
              key={k}
              icon={HAZARD_META[k].icon}
              label={HAZARD_META[k].label}
              pressed={kind === k}
              onClick={() => {
                go("auto");
                onAnswer(k);
              }}
            />
          ))}
        </div>
        <div className="mt-2 flex items-start justify-between gap-3">
          <p className="text-[11px] text-fg-subtle">Your press already saved where and when. This only says what.</p>
          <button type="button" onClick={() => go("closed")} className="-mx-2 -my-2 inline-flex min-h-8 shrink-0 items-center rounded px-2 text-[11px] font-medium text-fg-muted hover:text-fg">
            {kind ? "Keep it" : "Not now"}
          </button>
        </div>
        {errorLine ? <div className="mt-1.5">{errorLine}</div> : null}
      </div>
    );
  }

  if (kind) {
    return (
      <div ref={focus.ref} tabIndex={-1} className="space-y-1 rounded-lg bg-surface-2/60 px-2.5 py-2">
        <p className="flex items-center gap-2 text-xs text-fg">
          <CircleCheckBig className="size-3.5 shrink-0 text-good" aria-hidden />
          <span className="flex-1">Saved as {HAZARD_META[kind].label.toLowerCase()}, thanks.</span>
          <button type="button" onClick={() => go("open")} aria-label={`Change what this flag was (now: ${HAZARD_META[kind].label})`} className="-mx-2 -my-2 inline-flex min-h-8 shrink-0 items-center rounded px-2 text-[11px] font-medium text-accent-ink hover:underline">
            Change
          </button>
        </p>
        <p className="text-[11px] text-fg-muted">
          Next time, hold the button and say <span className="text-fg">{HAZARD_META[kind].keywords}</span> to skip this step (needs voice keywords on in{" "}
          <Link href="/app/profile#flag-button" className="text-accent-ink hover:underline">
            Clip settings
          </Link>
          ).
        </p>
        {errorLine}
      </div>
    );
  }

  return (
    <div ref={focus.ref} tabIndex={-1} className="space-y-1">
      <p className="flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-muted">
        <span>No word yet · it still marks the spot</span>
        <button type="button" onClick={() => go("open")} aria-expanded={false} className="-mx-2 -my-2 inline-flex min-h-8 items-center rounded px-2 font-medium text-accent-ink hover:underline">
          What was it?
        </button>
      </p>
      {errorLine}
    </div>
  );
}
