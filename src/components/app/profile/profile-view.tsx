"use client";

import {
  Activity,
  ArrowRight,
  Bike,
  Check,
  CircleDot,
  Flag,
  Gift,
  Lock,
  MapPinned,
  Megaphone,
  MessageSquareText,
  MoveHorizontal,
  Pencil,
  Scale,
  Share2,
  ShieldCheck,
  Sparkles,
  Sunrise,
  Trophy,
  Users,
  Waves,
  Wind,
  Wrench,
  Zap,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useEffect } from "react";
import { FLAG_SOURCE_LABEL, FLAG_STATUS_META, HAZARD_META } from "@/components/app/ride-events";
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
import { CITY_MIN_RIDERS, MAP_MIN_RIDERS } from "@/lib/reports";
import type { FlagReport, FlagStatus, ProfileStats } from "@/lib/types";
import { cn } from "@/lib/utils";
import { ClipSettings } from "./clip-settings";
import { PremiumCard } from "./premium-card";
import { PrivacySettings } from "./privacy-settings";

const RECORD_ICON: Record<string, LucideIcon> = { longest: MoveHorizontal, comfort: Waves, calm: Sparkles, fast: Zap };
const BADGE_ICON: Record<string, LucideIcon> = {
  cartographer: MapPinned,
  calm: Waves,
  pothole: CircleDot,
  fixed: Wrench,
  steward: ShieldCheck,
  early: Sunrise,
  clean: Wind,
  century: Trophy,
};

type ContributionStats = ProfileStats["contributions"];

const IMPACT: { key: keyof ContributionStats["impact"]; label: string; sub: string; icon: LucideIcon }[] = [
  { key: "ridersWarned", label: "Riders warned", sub: "saw your hazard before reaching it", icon: Megaphone },
  { key: "verified", label: "Flags verified", sub: "confirmed by other riders' Clips", icon: Users },
  { key: "fixed", label: "Fixes", sub: "repairs the Clips measured", icon: Wrench },
  { key: "causesGiven", label: "Causes given", sub: "hard brakes you explained", icon: MessageSquareText },
];

const CREDIT_RULES: { icon: LucideIcon; title: string; body: string }[] = [
  {
    icon: Users,
    title: "Outcomes, not presses",
    body: "Credit lands when other riders verify your flag or the city fixes it. The press itself earns nothing, so pressing twice changes nothing.",
  },
  { icon: Scale, title: "Every answer counts the same", body: "“Just me” included. Nobody gains by making a brake sound scarier than it was." },
  {
    icon: Gift,
    title: "Thank-yous arrive unannounced",
    body: "A Premium month, a tune-up at a partner bike shop. No points, no price list, and you can pass one on to a cause.",
  },
  { icon: ShieldCheck, title: "Warnings are free", body: "Verified hazards show for every rider, Premium or not." },
];

const SECTIONS = [
  { id: "overview", label: "Overview" },
  { id: "records", label: "Records" },
  { id: "badges", label: "Badges" },
  { id: "contributions", label: "Your mark" },
  { id: "clip", label: "Clip" },
  { id: "premium", label: "Premium" },
  { id: "privacy", label: "Privacy" },
];

const dateLabel = (iso: string) => formatDay(`${iso}T12:00:00Z`, { day: "numeric", month: "short", year: "numeric" });

function Records({ stats }: { stats: ProfileStats }) {
  return (
    <section id="records" aria-labelledby="records-title" className="scroll-mt-32">
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
    <section id="badges" aria-labelledby="badges-title" className="scroll-mt-32">
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

/** Flag status as a chip: an icon and a word, never colour alone. */
function FlagStatusChip({ status }: { status: FlagStatus }) {
  const meta = FLAG_STATUS_META[status];
  const Icon = meta.icon;
  return (
    <Badge variant={meta.tone === "good" ? "outline" : meta.tone} size="sm" className={cn(meta.tone === "good" && "border-good/30 bg-good-fill/10 text-good")}>
      <Icon aria-hidden /> {meta.label}
    </Badge>
  );
}

/** Where a flag stands on its way to everyone's map and the city. Riders = you + the Clips that confirmed it. */
function flagProgress(f: FlagReport) {
  const riders = f.confirmations + 1;
  const warned = `${formatInt(f.ridersWarned)} warned`;
  switch (f.status) {
    case "pending":
      return riders === 1 ? `Only you so far · on everyone's map at ${MAP_MIN_RIDERS} riders` : `${riders} of ${MAP_MIN_RIDERS} riders so far · on everyone's map at ${MAP_MIN_RIDERS}`;
    case "verified":
      return `${riders} riders · ${warned} · goes to the city at ${CITY_MIN_RIDERS}`;
    case "sent_to_city":
      return `${riders} riders · ${warned} · in the city's repair queue (IRIS)`;
    default:
      return `${riders} riders · ${warned}`;
  }
}

function ImpactCard({ c }: { c: ContributionStats }) {
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Impact</CardTitle>
          <p className="mt-0.5 text-xs text-fg-muted">What your flags and answers led to, since you started</p>
        </div>
        <Sparkles className="size-4 text-fg-subtle" aria-hidden />
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-4">
          {IMPACT.map((i) => (
            <StatTile key={i.key} label={i.label} value={formatInt(c.impact[i.key])} sub={i.sub} icon={<i.icon aria-hidden />} />
          ))}
        </div>
        <ul className="mt-5 flex flex-wrap gap-x-6 gap-y-2 border-t border-line pt-4 text-xs text-fg-muted">
          {[
            [c.streetsImproved, "segments refined this month"],
            [c.potholesConfirmed, "potholes confirmed"],
            [c.segmentsFirst, "streets you mapped first"],
          ].map(([v, l]) => (
            <li key={String(l)} className="flex items-baseline gap-1.5">
              <span className="font-num text-base font-semibold text-fg">{v}</span> {l}
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function YourFlags({ flags: all }: { flags: FlagReport[] }) {
  // Newest first, down to the minute (two flags can share a ride).
  const flags = [...all].sort((a, b) => `${b.date} ${b.time}`.localeCompare(`${a.date} ${a.time}`));
  const toName = flags.filter((f) => !f.kind).length;
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Your flags</CardTitle>
          <p className="mt-0.5 text-xs text-fg-muted">
            Dropped from the button on your Clip{toName ? ` · ${toName} still to name` : ""}
          </p>
        </div>
        <Flag className="size-4 text-fg-subtle" aria-hidden />
      </CardHeader>
      <CardContent className="pt-1">
        {flags.length === 0 ? (
          <p className="rounded-xl bg-surface-2 px-3 py-4 text-sm text-fg-muted">
            No flags yet. Press the button on your Clip when something&apos;s in the way, and it lands here after the ride.
          </p>
        ) : (
          <ul className="divide-y divide-line">
            {flags.map((f) => {
              const meta = f.kind ? HAZARD_META[f.kind] : null;
              const Icon = meta?.icon ?? Flag;
              const Source = FLAG_SOURCE_LABEL[f.source].icon;
              return (
                <li key={f.id} className="flex gap-3 py-3.5">
                  <span
                    className={cn("flex size-10 shrink-0 items-center justify-center rounded-xl text-fg", !meta && "border border-dashed border-line-strong bg-surface-2 text-fg-muted")}
                    style={meta ? { backgroundColor: `${meta.color}2e` } : undefined}
                    aria-hidden
                  >
                    <Icon className="size-[18px]" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center justify-between gap-x-3 gap-y-1">
                      <Link href={`/app/activities/${f.activityId}`} className="text-sm font-semibold text-fg hover:text-accent-ink">
                        {meta?.label ?? "Flag · no word said"}
                      </Link>
                      <FlagStatusChip status={f.status} />
                    </div>
                    <p className="mt-0.5 flex flex-wrap items-center gap-x-1.5 text-xs text-fg-muted">
                      <span>{f.street ?? "Unnamed street"}</span>
                      <span aria-hidden>·</span>
                      <span>
                        {formatDay(`${f.date}T12:00:00Z`, { day: "numeric", month: "short" })}, {f.time}
                      </span>
                      <span aria-hidden>·</span>
                      <span className="inline-flex items-center gap-1">
                        <Source className="size-3" aria-hidden /> {FLAG_SOURCE_LABEL[f.source].label}
                      </span>
                    </p>
                    <p className="mt-1 font-mono text-[11px] text-fg-subtle">{flagProgress(f)}</p>
                    {f.proof ? (
                      <p className="mt-2 flex items-start gap-2 rounded-lg bg-surface-2 px-2.5 py-1.5 text-xs text-fg">
                        <Activity className="mt-0.5 size-3.5 shrink-0 text-fg-muted" aria-hidden />
                        <span>
                          <span className="label-mono mr-1.5 text-fg-subtle">Clips measured</span>
                          {f.proof}
                        </span>
                      </p>
                    ) : null}
                    {!f.kind ? (
                      <Button asChild variant="secondary" size="sm" className="mt-2">
                        <Link href={`/app/activities/${f.activityId}#moments`}>
                          What was it? <ArrowRight />
                        </Link>
                      </Button>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function TrustCard({ trust }: { trust: ContributionStats["trust"] }) {
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Trust level</CardTitle>
          <p className="mt-0.5 text-xs text-fg-muted">How reliable your flags have been</p>
        </div>
        <Badge variant="neutral" size="sm">
          <Lock aria-hidden /> Private
        </Badge>
      </CardHeader>
      <CardContent>
        <p className="flex items-baseline gap-1.5">
          <span className="font-num text-4xl font-semibold text-fg">{trust.level}</span>
          <span className="text-sm text-fg-muted">/ {trust.max}</span>
        </p>
        <Progress value={trust.level} max={trust.max} label={`Trust level ${trust.level} of ${trust.max}`} className="mt-3 h-1.5" barClassName="bg-lane" />
        <p className="mt-2 flex items-center gap-1.5 text-xs text-fg-muted">
          <ArrowRight className="size-3.5 shrink-0" aria-hidden /> {trust.next}
        </p>
        <h4 className="mt-5 label-mono text-fg-subtle">Unlocked at your level</h4>
        <ul className="mt-2 space-y-2">
          {trust.perks.map((p) => (
            <li key={p} className="flex gap-2 text-sm text-fg">
              <Check className="mt-0.5 size-4 shrink-0 text-accent-ink" aria-hidden />
              {p}
            </li>
          ))}
        </ul>
        <p className="mt-5 flex gap-2 rounded-xl bg-surface-2 px-3 py-2.5 text-xs leading-5 text-fg-muted">
          <Lock className="mt-0.5 size-3.5 shrink-0" aria-hidden />
          <span>
            <span className="font-medium text-fg">Private — no leaderboard.</span> Only you see it. It rises when other riders verify your flags and the sensors agree with your answers, never with how often you press.
          </span>
        </p>
      </CardContent>
    </Card>
  );
}

function CreditRules() {
  return (
    <Card>
      <CardHeader>
        <CardTitle>How credit works</CardTitle>
        <Scale className="size-4 text-fg-subtle" aria-hidden />
      </CardHeader>
      <CardContent>
        <ul className="space-y-3.5">
          {CREDIT_RULES.map((r) => (
            <li key={r.title} className="flex gap-3">
              <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-surface-2 text-fg-muted" aria-hidden>
                <r.icon className="size-4" />
              </span>
              <div className="min-w-0">
                <p className="text-sm font-medium text-fg">{r.title}</p>
                <p className="mt-0.5 text-xs leading-5 text-fg-muted">{r.body}</p>
              </div>
            </li>
          ))}
        </ul>
      </CardContent>
    </Card>
  );
}

function Contributions({ stats }: { stats: ProfileStats }) {
  const c = stats.contributions;
  return (
    <section id="contributions" aria-labelledby="contributions-title" className="scroll-mt-32 space-y-6">
      <div>
        <h2 id="contributions-title" className="font-display text-xl font-semibold tracking-tight">
          Your mark on the map
        </h2>
        <p className="mt-1 text-sm text-fg-muted">What your flags, answers and rides changed on the street. Credit follows what happened, never the press.</p>
      </div>
      <ImpactCard c={c} />
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[minmax(0,1fr)_360px]">
        <YourFlags flags={c.flags} />
        <div className="space-y-6">
          <TrustCard trust={c.trust} />
          <CreditRules />
        </div>
      </div>
    </section>
  );
}

function TopStreets({ stats }: { stats: ProfileStats }) {
  const c = stats.contributions;
  const max = Math.max(...c.topStreets.map((s) => s.passes));
  return (
    <Card>
      <CardHeader>
        <div>
          <CardTitle>Streets you ride most</CardTitle>
          <p className="mt-0.5 text-xs text-fg-muted">Where your Clip has measured the most</p>
        </div>
        <MapPinned className="size-4 text-fg-subtle" aria-hidden />
      </CardHeader>
      <CardContent>
        <ul className="space-y-2.5">
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
  const ready = Boolean(stats.data && (clip.data || clip.error));

  // Deep links (#contributions, #clip, #flag-button, #premium, #privacy) land after the data has rendered.
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
              <div className="space-y-6">
                <Contributions stats={stats.data} />
                <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
                  <TopStreets stats={stats.data} />
                  <Clubs stats={stats.data} />
                </div>
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
