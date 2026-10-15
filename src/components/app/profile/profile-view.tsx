"use client";

import {
  Bike,
  CircleDot,
  Lock,
  MapPinned,
  MoveHorizontal,
  Pencil,
  Share2,
  Sparkles,
  Sunrise,
  Trophy,
  Users,
  Waves,
  Wind,
  Zap,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";
import { ErrorState } from "@/components/data/states";
import { StatTile } from "@/components/data/stat-tile";
import { Avatar } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { getClipStatus, getCurrentAthlete, getProfileStats } from "@/lib/api";
import { formatDay, formatInt, formatMonth } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";
import type { ProfileStats } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ClipSettings } from "./clip-settings";
import { PremiumCard } from "./premium-card";
import { PrivacySettings } from "./privacy-settings";

const RECORD_ICON: Record<string, LucideIcon> = { longest: MoveHorizontal, comfort: Waves, calm: Sparkles, fast: Zap };
const BADGE_ICON: Record<string, LucideIcon> = { cartographer: MapPinned, calm: Waves, pothole: CircleDot, early: Sunrise, clean: Wind, century: Trophy };

const SECTIONS = [
  { id: "overview", label: "Overview" },
  { id: "records", label: "Records" },
  { id: "badges", label: "Badges" },
  { id: "clip", label: "Clip" },
  { id: "premium", label: "Premium" },
  { id: "privacy", label: "Privacy" },
];

const dateLabel = (iso: string) => formatDay(`${iso}T12:00:00Z`, { day: "numeric", month: "short", year: "numeric" });

function Records({ stats }: { stats: ProfileStats }) {
  return (
    <section id="records" aria-labelledby="records-title" className="scroll-mt-24">
      <h2 id="records-title" className="font-display text-xl font-semibold tracking-tight">
        Personal records
      </h2>
      <ul className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {stats.records.map((r) => {
          const Icon = RECORD_ICON[r.id] ?? Trophy;
          return (
            <li key={r.id} className="rounded-2xl border border-line bg-surface p-4">
              <div className="flex items-center gap-2 text-xs text-fg-muted">
                <Icon className="size-4 text-accent-ink" aria-hidden />
                {r.label}
              </div>
              <p className="mt-2 font-num text-2xl font-semibold tracking-tight text-fg">{r.value}</p>
              <p className="mt-1 truncate text-xs text-fg-muted">{r.detail}</p>
              <p className="mt-2 font-mono text-[11px] text-fg-subtle">{dateLabel(r.date)}</p>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Badges({ stats }: { stats: ProfileStats }) {
  const earned = stats.badges.filter((b) => b.earned).length;
  return (
    <section id="badges" aria-labelledby="badges-title" className="scroll-mt-24">
      <div className="flex items-baseline justify-between">
        <h2 id="badges-title" className="font-display text-xl font-semibold tracking-tight">
          Badges
        </h2>
        <span className="text-sm text-fg-muted">
          <span className="font-num font-semibold text-fg">{earned}</span> of {stats.badges.length} earned
        </span>
      </div>
      <ul className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {stats.badges.map((b) => {
          const Icon = BADGE_ICON[b.id] ?? Trophy;
          return (
            <li key={b.id} className={cn("flex gap-4 rounded-2xl border p-4", b.earned ? "border-line bg-surface" : "border-dashed border-line-strong bg-transparent")}>
              <span
                className={cn(
                  "relative flex size-12 shrink-0 items-center justify-center rounded-2xl",
                  b.earned ? "bg-gradient-to-br from-signal to-signal-600 text-asphalt-900 shadow-[var(--shadow-glow)]" : "bg-surface-2 text-fg-subtle",
                )}
                aria-hidden
              >
                <Icon className="size-5" />
                {!b.earned ? (
                  <span className="absolute -right-1 -bottom-1 flex size-5 items-center justify-center rounded-full border border-line bg-surface">
                    <Lock className="size-2.5" />
                  </span>
                ) : null}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold text-fg">
                  {b.label}
                  <span className="sr-only">{b.earned ? ", earned" : ", not earned yet"}</span>
                </p>
                <p className="mt-0.5 text-xs leading-5 text-fg-muted">{b.description}</p>
                {!b.earned && b.progress !== undefined ? (
                  <div className="mt-2.5 flex items-center gap-2">
                    <Progress value={b.progress * 100} label={`${b.label} progress`} className="h-1.5" />
                    <span className="font-mono text-[11px] text-fg-muted">{Math.round(b.progress * 100)}%</span>
                  </div>
                ) : null}
              </div>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

function Contributions({ stats }: { stats: ProfileStats }) {
  const c = stats.contributions;
  const max = Math.max(...c.topStreets.map((s) => s.passes));
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Your mark on the map</CardTitle>
          <p className="mt-0.5 text-xs text-fg-muted">What your rides gave back to the city</p>
        </div>
        <MapPinned className="size-4 text-fg-subtle" aria-hidden />
      </CardHeader>
      <CardContent>
        <dl className="grid grid-cols-3 gap-3">
          {[
            [c.streetsImproved, "segments refined this month"],
            [c.potholesConfirmed, "potholes confirmed"],
            [c.segmentsFirst, "streets you mapped first"],
          ].map(([v, l]) => (
            <div key={String(l)} className="rounded-xl bg-surface-2 px-3 py-3">
              <dd className="font-num text-2xl font-semibold text-fg">{v}</dd>
              <dt className="mt-0.5 text-[11px] leading-4 text-fg-muted">{l}</dt>
            </div>
          ))}
        </dl>
        <h3 className="mt-5 text-xs font-medium text-fg-muted">Streets you ride most</h3>
        <ul className="mt-2 space-y-2.5">
          {c.topStreets.map((s) => (
            <li key={s.name}>
              <div className="flex justify-between gap-3 text-sm">
                <Link href={`/app/map?q=${encodeURIComponent(s.name)}`} className="truncate text-fg hover:text-accent-ink">
                  {s.name}
                </Link>
                <span className="font-mono text-xs text-fg-muted">{s.passes} passes</span>
              </div>
              <div className="mt-1 h-1.5 rounded-full bg-surface-2" aria-hidden>
                <div className="h-full rounded-full bg-lane" style={{ width: `${(s.passes / max) * 100}%` }} />
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function Clubs({ stats }: { stats: ProfileStats }) {
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Clubs</CardTitle>
          <p className="mt-0.5 text-xs text-fg-muted">October challenges</p>
        </div>
        <Users className="size-4 text-fg-subtle" aria-hidden />
      </CardHeader>
      <CardContent className="space-y-4">
        {stats.clubs.map((c) => (
          <div key={c.id} className="flex items-center gap-3">
            <Avatar name={c.name} size={40} />
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline justify-between gap-2">
                <p className="truncate text-sm font-medium">{c.name}</p>
                <span className="shrink-0 font-mono text-[11px] text-fg-muted">{Math.round((c.progress / c.goal) * 100)}%</span>
              </div>
              <p className="truncate text-xs text-fg-muted">
                {c.challenge} · {formatInt(c.progress)} / {formatInt(c.goal)} {c.unit} · {c.members} members
              </p>
              <Progress value={c.progress} max={c.goal} label={`${c.name}: ${c.challenge}`} className="mt-2 h-1.5" />
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

export function ProfileView() {
  const me = useApi(getCurrentAthlete);
  const stats = useApi(getProfileStats);
  const clip = useApi(getClipStatus);
  const ready = Boolean(stats.data);

  // Deep links (#clip, #premium, #privacy) land after the data has rendered.
  useEffect(() => {
    if (!ready || !window.location.hash) return;
    const el = document.getElementById(window.location.hash.slice(1));
    if (el) window.requestAnimationFrame(() => el.scrollIntoView({ block: "start" }));
  }, [ready]);

  const name = me.data?.name ?? "Laia Serra";
  const t = stats.data?.totals;

  return (
    <div className="mx-auto max-w-[1180px] px-4 py-6 sm:px-6 lg:py-8">
      <header id="overview" className="relative overflow-hidden rounded-3xl border border-line bg-surface p-5 sm:p-7">
        <div aria-hidden className="absolute -top-24 -right-20 size-72 rounded-full bg-signal/10 blur-3xl" />
        <div className="relative flex flex-col gap-5 sm:flex-row sm:items-center">
          <Avatar name={name} initials={me.data?.initials} size={84} className="ring-4 ring-surface-2" />
          <div className="min-w-0 flex-1">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-display text-3xl font-semibold tracking-tight">{name}</h1>
              <Badge variant="neutral" size="sm">
                Free plan
              </Badge>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-x-2 text-sm text-fg-muted">
              {me.data ? (
                <>
                  <span>{me.data.age}</span>
                  <span aria-hidden>·</span>
                  <span>{me.data.city}</span>
                  <span aria-hidden>·</span>
                  <span className="inline-flex items-center gap-1">
                    <Bike className="size-3.5" aria-hidden /> {me.data.vehicle[0].toUpperCase() + me.data.vehicle.slice(1)} commuter
                  </span>
                </>
              ) : (
                <Skeleton className="h-4 w-56" />
              )}
            </div>
            {t ? <p className="mt-1 text-xs text-fg-subtle">Riding with UMI since {formatMonth(t.since.slice(0, 7), "long")}</p> : null}
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm">
              <Pencil /> Edit profile
            </Button>
            <Button variant="secondary" size="icon-sm" aria-label="Share profile">
              <Share2 />
            </Button>
          </div>
        </div>
        <div className="relative mt-6 grid grid-cols-2 gap-x-6 gap-y-4 border-t border-line pt-5 sm:grid-cols-4">
          {t ? (
            <>
              <StatTile label="Distance" value={formatInt(t.distanceKm)} unit="km" />
              <StatTile label="Activities" value={formatInt(t.rides + t.runs)} sub={`${t.rides} rides · ${t.runs} runs`} />
              <StatTile label="Time" value={t.hours} unit="h" />
              <StatTile label="Streets mapped" value={t.streetsMapped} />
            </>
          ) : (
            [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-14" />)
          )}
        </div>
      </header>

      <nav aria-label="Profile sections" className="sticky top-16 z-20 -mx-4 mt-4 bg-bg/85 px-4 py-2 backdrop-blur-xl sm:-mx-6 sm:px-6">
        <ul className="scrollbar-none flex gap-1 overflow-x-auto">
          {SECTIONS.map((s) => (
            <li key={s.id}>
              <a href={`#${s.id}`} className="inline-flex h-8 items-center rounded-full px-3 text-sm whitespace-nowrap text-fg-muted transition-colors hover:bg-surface-2 hover:text-fg">
                {s.label}
              </a>
            </li>
          ))}
        </ul>
      </nav>

      {stats.error ? (
        <ErrorState error={stats.error} onRetry={stats.retry} className="mt-6" />
      ) : (
        <div className="mt-4 space-y-10">
          {stats.data ? (
            <>
              <Records stats={stats.data} />
              <Badges stats={stats.data} />
              <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                <Contributions stats={stats.data} />
                <Clubs stats={stats.data} />
              </div>
            </>
          ) : (
            <div className="space-y-4" aria-busy="true" aria-label="Loading your profile">
              <Skeleton className="h-6 w-48" />
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
                {[0, 1, 2, 3].map((i) => (
                  <Skeleton key={i} className="h-32 rounded-2xl" />
                ))}
              </div>
            </div>
          )}
          <ClipSettings clip={clip.data} />
          <PremiumCard />
          <PrivacySettings />
        </div>
      )}
    </div>
  );
}
