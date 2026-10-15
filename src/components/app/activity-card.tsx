"use client";

import { Bike, Footprints, Hand, MessageCircle, Share2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ScorePills } from "@/components/score/score-badge";
import { Avatar } from "@/components/ui/avatar";
import { Card } from "@/components/ui/card";
import { formatActivityDate, formatDuration, formatKm, formatPace } from "@/lib/format";
import { mockNow } from "@/lib/mock";
import type { ActivitySummary, Athlete, RideEventType } from "@/lib/types";
import { cn } from "@/lib/utils";
import { RouteThumb } from "./route-thumb";

const EVENT_LABEL: Record<RideEventType, [string, string]> = {
  hard_brake: ["hard brake", "hard brakes"],
  pothole: ["pothole", "potholes"],
  pm_spike: ["PM2.5 spike", "PM2.5 spikes"],
  noise_peak: ["noise peak", "noise peaks"],
};

export function eventSummary(events: ActivitySummary["events"]) {
  const counts = new Map<RideEventType, number>();
  for (const e of events) counts.set(e.type, (counts.get(e.type) ?? 0) + 1);
  return [...counts.entries()].map(([t, n]) => `${n} ${EVENT_LABEL[t][n === 1 ? 0 : 1]}`).join(" · ");
}

export function ActivityCard({ activity, athlete, isOwn }: { activity: ActivitySummary; athlete: Athlete; isOwn: boolean }) {
  const [kudoed, setKudoed] = useState(false);
  const kudos = activity.kudos + (kudoed ? 1 : 0);
  const Icon = activity.type === "ride" ? Bike : Footprints;
  const href = `/app/activities/${activity.id}`;
  const events = eventSummary(activity.events);

  return (
    <Card className="overflow-hidden" aria-labelledby={`act-${activity.id}`}>
      <div className="flex items-start gap-3 px-5 pt-5">
        <Avatar name={athlete.name} initials={athlete.initials} size={40} />
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2 text-sm">
            <span className="font-semibold text-fg">{athlete.name}</span>
            {!isOwn ? <span className="rounded-full bg-surface-2 px-2 py-0.5 text-[11px] text-fg-muted">Following</span> : null}
          </div>
          <p className="mt-0.5 flex items-center gap-1.5 text-xs text-fg-muted">
            <Icon className="size-3.5" aria-label={activity.type === "ride" ? "E-bike ride" : "Run"} />
            <time dateTime={activity.startedAt}>{formatActivityDate(activity.startedAt, mockNow())}</time>
            <span aria-hidden>·</span>
            <span className="truncate">{activity.place}</span>
          </p>
        </div>
      </div>

      <div className="px-5 pt-3">
        <h3 id={`act-${activity.id}`} className="font-display text-lg font-semibold tracking-tight">
          <Link href={href} className="rounded-md text-fg hover:text-accent-ink">
            {activity.title}
          </Link>
        </h3>
        {activity.description ? <p className="mt-1 text-sm text-fg-muted">{activity.description}</p> : null}
        <dl className="mt-3 flex gap-6">
          <div>
            <dt className="text-[11px] text-fg-subtle">Distance</dt>
            <dd className="font-num text-lg font-semibold">{formatKm(activity.distanceM)}</dd>
          </div>
          <div>
            <dt className="text-[11px] text-fg-subtle">{activity.type === "run" ? "Pace" : "Avg speed"}</dt>
            <dd className="font-num text-lg font-semibold">
              {activity.type === "run" ? formatPace(activity.distanceM, activity.movingTimeS) : `${activity.avgSpeedKmh.toFixed(1)} km/h`}
            </dd>
          </div>
          <div>
            <dt className="text-[11px] text-fg-subtle">Time</dt>
            <dd className="font-num text-lg font-semibold">{formatDuration(activity.movingTimeS)}</dd>
          </div>
        </dl>
      </div>

      <Link href={href} className="mt-4 block border-y border-line" tabIndex={-1} aria-hidden>
        <RouteThumb coordinates={activity.preview} label="" height={220} />
      </Link>

      <div className="flex flex-wrap items-center gap-x-4 gap-y-2 px-5 pt-4">
        <ScorePills scores={activity.scores} />
        {events ? <p className="text-xs text-fg-muted">{events}</p> : <p className="text-xs text-fg-subtle">No incidents recorded</p>}
      </div>

      <div className="mt-4 flex items-center gap-1 border-t border-line px-3 py-2">
        <button
          type="button"
          onClick={() => setKudoed((k) => !k)}
          aria-pressed={kudoed}
          className={cn(
            "inline-flex h-9 items-center gap-2 rounded-xl px-3 text-sm transition-colors",
            kudoed ? "text-accent-ink" : "text-fg-muted hover:bg-surface-2 hover:text-fg",
          )}
        >
          <Hand className={cn("size-4 transition-transform", kudoed && "scale-110 fill-current")} />
          <span className="font-num">{kudos}</span>
          <span className="sr-only">kudos{kudoed ? ", you gave kudos" : ""}</span>
        </button>
        <Link href={`${href}#comments`} className="inline-flex h-9 items-center gap-2 rounded-xl px-3 text-sm text-fg-muted hover:bg-surface-2 hover:text-fg">
          <MessageCircle className="size-4" />
          <span className="font-num">{activity.comments}</span>
          <span className="sr-only">comments</span>
        </Link>
        <div className="ml-auto flex -space-x-2" aria-label={`Kudos from ${activity.kudoedBy.slice(0, 3).join(", ")}`}>
          {activity.kudoedBy.slice(0, 3).map((n) => (
            <Avatar key={n} name={n} size={24} className="ring-surface" />
          ))}
        </div>
        <button type="button" className="ml-2 inline-flex size-9 items-center justify-center rounded-xl text-fg-muted hover:bg-surface-2 hover:text-fg" aria-label="Share">
          <Share2 className="size-4" />
        </button>
      </div>
    </Card>
  );
}

export function ActivityCardSkeleton() {
  return (
    <Card className="overflow-hidden p-5" aria-hidden>
      <div className="flex items-center gap-3">
        <div className="size-10 animate-pulse rounded-full bg-surface-2" />
        <div className="space-y-2">
          <div className="h-3 w-32 animate-pulse rounded bg-surface-2" />
          <div className="h-2.5 w-48 animate-pulse rounded bg-surface-2" />
        </div>
      </div>
      <div className="mt-5 h-4 w-44 animate-pulse rounded bg-surface-2" />
      <div className="mt-4 flex gap-6">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-8 w-16 animate-pulse rounded bg-surface-2" />
        ))}
      </div>
      <div className="mt-4 h-48 animate-pulse rounded-xl bg-surface-2" />
    </Card>
  );
}
