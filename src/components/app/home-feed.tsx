"use client";

import { Award, Bike, Clock, Flame, MapPinned, RefreshCw, Users, Wind } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { ClipBattery } from "@/components/shell/clip-battery";
import { EmptyState, ErrorState } from "@/components/data/states";
import { StatTile } from "@/components/data/stat-tile";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { getAthlete, getBestWindow, getClipStatus, getCurrentAthlete, getFeed, getProfileStats, getWeekStats } from "@/lib/api";
import { formatDay, formatDuration, formatRelative, greeting } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";
import { mockNow } from "@/lib/mock";
import type { Athlete } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ActivityCard, ActivityCardSkeleton } from "./activity-card";

// PM2.5 forecast along Laia's usual route today (µg/m³, by hour).
const TODAY_PM = [9, 8, 8, 8, 9, 11, 15, 21, 24, 20, 16, 14, 13, 12, 11, 11, 12, 13, 9.5, 9, 10, 10.5, 10, 9];
const WINDOW = [18, 19];

function BestWindowCard() {
  const { data } = useApi(getBestWindow);
  const max = Math.max(...TODAY_PM);
  return (
    <Card className="relative overflow-hidden">
      <div aria-hidden className="absolute -top-16 -right-16 size-48 rounded-full bg-signal/15 blur-3xl" />
      <CardContent className="relative pt-5">
        <div className="flex items-center gap-2 label-mono text-accent-ink">
          <Wind className="size-3.5" /> {data?.title ?? "Today's best window"}
        </div>
        <p className="mt-3 font-display text-2xl font-semibold tracking-tight">
          Cleanest air <span className="text-accent-ink">{data?.window ?? "18:00–19:30"}</span>
        </p>
        <p className="mt-1.5 max-w-md text-sm text-fg-muted">{data?.detail ?? "Loading today's forecast…"}</p>
        <div className="mt-4 flex h-16 items-end gap-[3px]" role="img" aria-label="PM2.5 forecast by hour today, lowest between 18:00 and 19:30">
          {TODAY_PM.map((v, h) => {
            const inWindow = h >= WINDOW[0] && h <= WINDOW[1];
            return (
              <div key={h} className="flex flex-1 flex-col items-center gap-1">
                <div
                  className={cn("w-full rounded-sm", inWindow ? "bg-signal" : v > 15 ? "bg-bad-fill/40" : "bg-surface-3")}
                  style={{ height: `${(v / max) * 48}px` }}
                />
              </div>
            );
          })}
        </div>
        <div className="mt-1 flex justify-between font-mono text-[10px] text-fg-subtle">
          <span>00</span>
          <span>06</span>
          <span>12</span>
          <span>18</span>
          <span>23</span>
        </div>
      </CardContent>
    </Card>
  );
}

function WeekStats() {
  const { data, loading } = useApi(getWeekStats);
  if (loading && !data) return <Skeleton className="h-[188px] rounded-2xl" />;
  if (!data) return null;
  const maxDay = Math.max(1, ...data.days.map((d) => d.km));
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>This week</CardTitle>
          <p className="mt-0.5 text-xs text-fg-muted">Rides and runs since Monday</p>
        </div>
        <span className="inline-flex items-center gap-1.5 rounded-full bg-signal/12 px-2.5 py-1 text-xs font-medium text-accent-ink">
          <Flame className="size-3.5" /> {data.streakDays}-day streak
        </span>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-3 gap-4">
          <StatTile label="Distance" value={data.distanceKm.toFixed(1)} unit="km" />
          <StatTile label="Moving time" value={formatDuration(data.movingTimeS).replace(/ \d+s$/, "")} />
          <StatTile label="Activities" value={data.rides + data.runs} sub={`${data.rides} rides · ${data.runs} runs`} />
        </div>
        <div className="mt-5">
          <div className="flex justify-between text-xs">
            <span className="text-fg-muted">Weekly goal</span>
            <span className="font-mono text-fg">
              {data.distanceKm.toFixed(1)} / {data.goalKm} km
            </span>
          </div>
          <Progress value={data.distanceKm} max={data.goalKm} label="Weekly distance goal" className="mt-2" />
        </div>
        <div className="mt-4 grid grid-cols-7 gap-1.5" role="img" aria-label={`Distance per day: ${data.days.map((d) => `${d.label} ${d.km} km`).join(", ")}`}>
          {data.days.map((d, i) => (
            <div key={i} className="flex flex-col items-center gap-1">
              <div className="flex h-9 w-full max-w-7 items-end overflow-hidden rounded-md bg-surface-2">
                <div className={cn("w-full rounded-md", d.isToday ? "bg-signal" : "bg-fg/25")} style={{ height: `${(d.km / maxDay) * 100}%` }} />
              </div>
              <span className={cn("font-mono text-[10px]", d.isToday ? "text-accent-ink" : "text-fg-subtle")}>{d.label}</span>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function MiniProfile({ me }: { me?: Athlete }) {
  return (
    <Card>
      <CardContent className="pt-5">
        <div className="flex items-center gap-3">
          <Avatar name={me?.name ?? "Laia Serra"} initials={me?.initials} size={48} />
          <div>
            <p className="font-display font-semibold">{me?.name ?? "Laia Serra"}</p>
            <p className="text-xs text-fg-muted">{me ? `${me.city} · ${me.vehicle}` : "Gràcia, Barcelona"}</p>
          </div>
        </div>
        <dl className="mt-4 grid grid-cols-3 gap-2 text-center">
          {[
            ["Following", "96"],
            ["Followers", "128"],
            ["Rides", "412"],
          ].map(([k, v]) => (
            <div key={k} className="rounded-xl bg-surface-2 py-2">
              <dd className="font-num text-base font-semibold">{v}</dd>
              <dt className="text-[11px] text-fg-muted">{k}</dt>
            </div>
          ))}
        </dl>
      </CardContent>
    </Card>
  );
}

function ClipCard() {
  const { data } = useApi(getClipStatus);
  const [syncing, setSyncing] = useState(false);
  const [synced, setSynced] = useState<string | null>(null);
  return (
    <Card id="clip-card">
      <CardHeader>
        <CardTitle>UMI Clip</CardTitle>
        <span className="inline-flex items-center gap-1.5 text-xs text-good">
          <span className="size-1.5 rounded-full bg-good-fill" /> Connected
        </span>
      </CardHeader>
      <CardContent>
        {data ? (
          <>
            <div className="flex items-center justify-between">
              <ClipBattery level={data.battery} />
              <span className="text-xs text-fg-muted">≈ 5 days left</span>
            </div>
            <dl className="mt-3 space-y-1.5 text-xs">
              <div className="flex justify-between">
                <dt className="text-fg-muted">Last sync</dt>
                <dd>{synced ? "just now" : formatRelative(data.lastSync, mockNow())}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-fg-muted">Firmware</dt>
                <dd className="font-mono">{data.firmware}</dd>
              </div>
            </dl>
            <Button
              variant="secondary"
              size="sm"
              className="mt-4 w-full"
              disabled={syncing}
              onClick={() => {
                setSyncing(true);
                setTimeout(() => {
                  setSyncing(false);
                  setSynced("now");
                }, 1400);
              }}
            >
              <RefreshCw className={cn(syncing && "animate-spin")} /> {syncing ? "Syncing…" : "Sync now"}
            </Button>
          </>
        ) : (
          <Skeleton className="h-24" />
        )}
      </CardContent>
    </Card>
  );
}

function StreetsImproved() {
  const { data } = useApi(getProfileStats);
  const c = data?.contributions;
  const max = c ? Math.max(...c.topStreets.map((s) => s.passes)) : 1;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Streets you improved</CardTitle>
        <MapPinned className="size-4 text-fg-subtle" aria-hidden />
      </CardHeader>
      <CardContent>
        {c ? (
          <>
            <p className="text-sm text-fg-muted">
              Your rides refined <span className="font-semibold text-fg">{c.streetsImproved} street segments</span> this month and confirmed{" "}
              <span className="font-semibold text-fg">{c.potholesConfirmed} potholes</span> for the city.
            </p>
            <ul className="mt-4 space-y-2.5">
              {c.topStreets.map((s) => (
                <li key={s.name}>
                  <div className="flex justify-between text-xs">
                    <span className="truncate">{s.name}</span>
                    <span className="font-mono text-fg-muted">{s.passes} passes</span>
                  </div>
                  <div className="mt-1 h-1.5 rounded-full bg-surface-2">
                    <div className="h-full rounded-full bg-lane" style={{ width: `${(s.passes / max) * 100}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          </>
        ) : (
          <Skeleton className="h-32" />
        )}
      </CardContent>
    </Card>
  );
}

function Clubs() {
  const { data } = useApi(getProfileStats);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Club challenges</CardTitle>
        <Users className="size-4 text-fg-subtle" aria-hidden />
      </CardHeader>
      <CardContent className="space-y-4">
        {data
          ? data.clubs.map((c) => (
              <div key={c.id}>
                <div className="flex items-baseline justify-between gap-2">
                  <p className="truncate text-sm font-medium">{c.name}</p>
                  <span className="shrink-0 font-mono text-[11px] text-fg-muted">{Math.round((c.progress / c.goal) * 100)}%</span>
                </div>
                <p className="text-xs text-fg-muted">
                  {c.challenge} · {c.progress.toLocaleString("en-US")} / {c.goal.toLocaleString("en-US")} {c.unit}
                </p>
                <Progress value={c.progress} max={c.goal} label={`${c.name} progress`} className="mt-2 h-1.5" />
              </div>
            ))
          : [0, 1, 2].map((i) => <Skeleton key={i} className="h-12" />)}
      </CardContent>
    </Card>
  );
}

export function HomeFeed() {
  const me = useApi(getCurrentAthlete);
  const feed = useApi(getFeed);
  const marc = useApi(() => getAthlete("marc"));
  const [visible, setVisible] = useState(8);
  const people = useMemo(() => {
    const map: Record<string, Athlete> = {};
    if (me.data) map[me.data.id] = me.data;
    if (marc.data) map[marc.data.id] = marc.data;
    return map;
  }, [me.data, marc.data]);
  const now = mockNow();

  return (
    <div className="mx-auto grid grid-cols-1 max-w-[1180px] gap-6 px-4 py-6 sm:px-6 lg:py-8 xl:grid-cols-[minmax(0,1fr)_320px]">
      <div className="min-w-0 space-y-6">
        <header>
          <p className="text-sm text-fg-muted">{formatDay(now.toISOString())}</p>
          <h1 className="mt-1 font-display text-3xl font-semibold tracking-tight sm:text-4xl">
            {greeting()}, {me.data?.firstName ?? "Laia"}
          </h1>
        </header>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <BestWindowCard />
          <WeekStats />
        </div>

        <section aria-labelledby="feed-title" className="space-y-4">
          <div className="flex items-center justify-between">
            <h2 id="feed-title" className="font-display text-lg font-semibold">
              Activity
            </h2>
            <Link href="/app/routes" className="inline-flex items-center gap-1.5 text-sm text-accent-ink hover:underline">
              <Bike className="size-4" /> Plan tomorrow&apos;s ride
            </Link>
          </div>
          {feed.error ? (
            <ErrorState error={feed.error} onRetry={feed.retry} />
          ) : feed.loading && !feed.data ? (
            <>
              <ActivityCardSkeleton />
              <ActivityCardSkeleton />
            </>
          ) : feed.data && feed.data.length === 0 ? (
            <EmptyState
              icon={<Award />}
              title="No rides yet"
              body="Clip UMI on your bike, scooter or running belt and your first ride report will appear here after the next sync."
              action={
                <Button asChild variant="secondary" size="sm">
                  <Link href="/app/profile#clip">Set up your Clip</Link>
                </Button>
              }
            />
          ) : (
            <>
              {feed.data!.slice(0, visible).map((a) => (
                <ActivityCard key={a.id} activity={a} athlete={people[a.athleteId] ?? { id: a.athleteId, name: "Rider", firstName: "Rider", initials: "R", age: 0, city: "", vehicle: "" }} isOwn={a.athleteId === "laia"} />
              ))}
              {visible < feed.data!.length ? (
                <div className="flex justify-center">
                  <Button variant="secondary" onClick={() => setVisible((v) => v + 8)}>
                    <Clock /> Show older activities
                  </Button>
                </div>
              ) : null}
            </>
          )}
        </section>
      </div>

      <aside className="space-y-4 xl:sticky xl:top-[88px] xl:self-start" aria-label="Your profile and Clip">
        <MiniProfile me={me.data} />
        <ClipCard />
        <StreetsImproved />
        <Clubs />
      </aside>
    </div>
  );
}
