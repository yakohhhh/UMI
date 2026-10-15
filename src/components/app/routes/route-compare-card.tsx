"use client";

import { Check, Leaf, Navigation, Timer, Waves } from "lucide-react";
import { useState } from "react";
import { ScorePills } from "@/components/score/score-badge";
import { ScoreRing } from "@/components/score/score-gauge";
import { Button } from "@/components/ui/button";
import { formatKm, shortStreet } from "@/lib/format";
import { bandLabel, overallScore } from "@/lib/score";
import type { PlannedRoute } from "@/lib/types";
import { cn } from "@/lib/utils";

export const GOAL_META: Record<PlannedRoute["goal"], { icon: typeof Timer; cta: string; blurb: string }> = {
  fastest: { icon: Timer, cta: "Go fast", blurb: "Shortest time, whatever the street" },
  calmest: { icon: Waves, cta: "Go calm", blurb: "Smooth, quiet streets with fewer hard brakes" },
  cleanest: { icon: Leaf, cta: "Go clean", blurb: "Lowest PM2.5 forecast for your departure" },
};

/**
 * One route alternative. The whole card selects the route (stretched button);
 * the CTA inside sends it to the phone.
 */
export function RouteCompareCard({
  route,
  baseline,
  selected,
  onSelect,
  viaHighlight,
  className,
}: {
  route: PlannedRoute;
  /** Usually the fastest route: deltas are shown against it. */
  baseline?: PlannedRoute;
  selected: boolean;
  onSelect: () => void;
  /** Street name to emphasise in the "via" line. */
  viaHighlight?: string | null;
  className?: string;
}) {
  const [sent, setSent] = useState(false);
  const meta = GOAL_META[route.goal];
  const overall = overallScore(route.scores);
  const dt = baseline && baseline.id !== route.id ? route.durationMin - baseline.durationMin : null;
  const Icon = meta.icon;

  return (
    <article
      className={cn(
        "relative rounded-2xl border bg-surface p-4 transition-[border-color,box-shadow] duration-200",
        selected ? "border-signal/60 shadow-[0_0_0_1px_rgb(255_91_31/0.35),var(--shadow-soft)]" : "border-line hover:border-line-strong",
        className,
      )}
      aria-labelledby={`route-${route.id}`}
    >
      <button
        type="button"
        onClick={onSelect}
        aria-pressed={selected}
        aria-label={`Show the ${route.label.toLowerCase()} route on the map: ${route.durationMin} minutes, overall score ${overall}`}
        className="absolute inset-0 z-0 rounded-2xl"
      />
      <div className="pointer-events-none relative">
        <div className="flex items-start gap-3">
          <span
            className={cn("flex size-9 shrink-0 items-center justify-center rounded-xl", selected ? "bg-signal text-asphalt-900" : "bg-surface-2 text-fg-muted")}
            aria-hidden
          >
            <Icon className="size-[18px]" />
          </span>
          <div className="min-w-0 flex-1">
            <h3 id={`route-${route.id}`} className="flex items-center gap-2 text-sm font-semibold text-fg">
              {route.label}
              {selected ? <span className="h-1 w-5 rounded-full bg-signal" aria-hidden /> : <span className="h-1 w-5 rounded-full bg-fg-subtle/50" aria-hidden />}
            </h3>
            <p className="mt-0.5 flex flex-wrap items-baseline gap-x-2 text-xs text-fg-muted">
              <span className="font-num text-2xl leading-7 font-semibold text-fg">
                {route.durationMin}
                <span className="ml-0.5 text-sm font-medium text-fg-muted">min</span>
              </span>
              {dt !== null ? <span className={cn("font-num font-semibold", dt > 0 ? "text-fg" : "text-good")}>{dt > 0 ? `+${dt} min` : dt < 0 ? `${dt} min` : "same time"}</span> : <span>quickest</span>}
              <span aria-hidden>·</span>
              <span className="font-num">{formatKm(route.distanceM)}</span>
            </p>
          </div>
          <ScoreRing score={overall} size={46} stroke={4.5} label={`Overall ${overall}, ${bandLabel(overall)}`} />
        </div>

        <p className="mt-3 line-clamp-2 text-xs leading-5 text-fg-muted">
          via{" "}
          {route.via.map((v, i) => (
            <span key={v}>
              <span className={cn(viaHighlight && v === viaHighlight ? "font-semibold text-fg" : undefined)}>{shortStreet(v)}</span>
              {i < route.via.length - 1 ? <span aria-hidden> · </span> : null}
            </span>
          ))}
        </p>

        <ScorePills scores={route.scores} className="mt-3" />

        <p className="mt-3 text-xs text-fg">
          <span className="text-accent-ink" aria-hidden>
            ✦{" "}
          </span>
          {route.highlight}
        </p>
      </div>

      {selected ? (
        <div className="relative z-10 mt-4 flex items-center gap-2">
          <Button size="sm" onClick={() => setSent(true)} className="flex-1" variant={sent ? "secondary" : "primary"} aria-live="polite">
            {sent ? (
              <>
                <Check /> Sent to your phone
              </>
            ) : (
              <>
                <Navigation /> {meta.cta}
              </>
            )}
          </Button>
        </div>
      ) : null}
    </article>
  );
}

export function RouteCompareCardSkeleton() {
  return (
    <div className="rounded-2xl border border-line bg-surface p-4" aria-hidden>
      <div className="flex items-start gap-3">
        <div className="size-9 animate-pulse rounded-xl bg-surface-2" />
        <div className="flex-1 space-y-2">
          <div className="h-3 w-20 animate-pulse rounded bg-surface-2" />
          <div className="h-6 w-28 animate-pulse rounded bg-surface-2" />
        </div>
        <div className="size-11 animate-pulse rounded-full bg-surface-2" />
      </div>
      <div className="mt-4 h-3 w-full animate-pulse rounded bg-surface-2" />
      <div className="mt-3 flex gap-1.5">
        {[0, 1, 2, 3].map((i) => (
          <div key={i} className="h-6 w-12 animate-pulse rounded-full bg-surface-2" />
        ))}
      </div>
    </div>
  );
}
