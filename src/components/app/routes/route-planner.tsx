"use client";

import { ArrowUpDown, Clock, Loader2, MapPin, Sparkles, X } from "lucide-react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/segmented";
import { Skeleton } from "@/components/ui/skeleton";
import { getStreetSegments, planRoutes, type RouteRequest } from "@/lib/api";
import { formatTime } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";
import { mockNow } from "@/lib/mock";
import { overallScore } from "@/lib/score";
import type { PlannedRoute } from "@/lib/types";
import { cn } from "@/lib/utils";
import { GOAL_META, RouteCompareCard, RouteCompareCardSkeleton } from "./route-compare-card";

const RoutesMap = dynamic(() => import("./routes-map"), {
  ssr: false,
  loading: () => <Skeleton className="size-full rounded-none" />,
});

const HOME = "Plaça de la Vila de Gràcia";
const WORK = "Carrer de Pallars, 22@";
const GOALS: PlannedRoute["goal"][] = ["fastest", "calmest", "cleanest"];

function CalmNudge({ routes, selected, onPick }: { routes: PlannedRoute[]; selected: PlannedRoute["goal"]; onPick: (g: PlannedRoute["goal"]) => void }) {
  const fast = routes.find((r) => r.goal === "fastest");
  const calm = routes.find((r) => r.goal === "calmest");
  if (!fast || !calm) return null;
  const dt = calm.durationMin - fast.durationMin;
  const gain = overallScore(calm.scores) - overallScore(fast.scores);
  const far = gain >= 15;
  const onCalm = selected === "calmest";
  return (
    <section
      aria-live="polite"
      className={cn("relative overflow-hidden rounded-2xl border p-4", onCalm ? "border-good-fill/30 bg-good-fill/[0.07]" : "border-signal/30 bg-signal/[0.07]")}
    >
      <div aria-hidden className={cn("absolute -top-12 -right-10 size-36 rounded-full blur-3xl", onCalm ? "bg-good-fill/20" : "bg-signal/20")} />
      <div className="relative flex items-start gap-3">
        <div className="min-w-0 flex-1">
          <p className="font-display text-lg leading-snug font-semibold tracking-tight text-fg">
            {onCalm ? (
              <>You picked the calm way.</>
            ) : dt > 0 ? (
              <>
                <span className="font-num text-accent-ink">+{dt} min</span> for a {far ? "far " : ""}calmer ride
              </>
            ) : (
              <>The calmest route is just as quick right now</>
            )}
          </p>
          <p className="mt-1 text-sm text-fg-muted">
            {onCalm
              ? `${gain} points calmer than the fastest route for ${dt > 0 ? `${dt} more minute${dt === 1 ? "" : "s"}` : "no extra time"}.`
              : `Overall ${overallScore(calm.scores)} instead of ${overallScore(fast.scores)}: safety ${calm.scores.safety} vs ${fast.scores.safety}, noise ${calm.scores.noise} vs ${fast.scores.noise}.`}
          </p>
        </div>
        {!onCalm ? (
          <Button size="sm" onClick={() => onPick("calmest")} className="shrink-0">
            {GOAL_META.calmest.cta}
          </Button>
        ) : null}
      </div>
    </section>
  );
}

export function RoutePlanner() {
  const params = useSearchParams();
  const viaId = params.get("via");
  const [from, setFrom] = useState(HOME);
  const [to, setTo] = useState(WORK);
  const [departAt, setDepartAt] = useState("08:00");
  const [via, setVia] = useState<string | null>(viaId);
  const [request, setRequest] = useState<RouteRequest>({ from: HOME, to: WORK, departAt: "08:00", via: viaId });
  const [goal, setGoal] = useState<PlannedRoute["goal"]>("fastest");

  const plan = useApi(() => planRoutes(request), [request.from, request.to, request.departAt, request.via]);
  const streets = useApi(getStreetSegments);
  const viaName = via ? (streets.data?.find((s) => s.id === via)?.name ?? null) : null;

  // The mock alternatives run Gràcia → 22@; a swapped trip is the same streets backwards.
  const reversed = request.from === WORK || (request.from !== HOME && request.to === HOME);
  const routes = useMemo(
    () => (plan.data ?? []).map((r) => (reversed ? { ...r, coordinates: [...r.coordinates].reverse(), via: [...r.via].reverse() } : r)),
    [plan.data, reversed],
  );
  const selected = routes.find((r) => r.goal === goal) ?? routes[0];
  const fastest = routes.find((r) => r.goal === "fastest");

  const submit = (next: Partial<RouteRequest> = {}) => setRequest({ from, to, departAt, via, ...next });

  const swap = () => {
    setFrom(to);
    setTo(from);
    submit({ from: to, to: from });
  };

  const updating = plan.loading && Boolean(plan.data);

  return (
    <div className="flex flex-col pb-24 lg:h-[calc(100dvh-4rem-1px)] lg:flex-row lg:pb-0">
      <div className="contents lg:flex lg:w-[440px] lg:shrink-0 lg:flex-col lg:overflow-y-auto lg:border-r lg:border-line lg:bg-bg-elevated xl:w-[480px]">
        <div className="order-1 px-4 pt-6 sm:px-6 lg:pt-7">
          <h1 className="font-display text-3xl font-semibold tracking-tight">Routes</h1>
          <p className="mt-1 text-sm text-fg-muted">The fastest way, the calmest way, the cleanest way. You choose.</p>

          <form
            className="mt-5 rounded-2xl border border-line bg-surface p-2"
            onSubmit={(e) => {
              e.preventDefault();
              submit();
            }}
            aria-label="Plan a route"
          >
            <div className="relative pr-12">
              <div className="flex items-center gap-3 rounded-xl px-2 focus-within:bg-surface-2">
                <span className="size-3 shrink-0 rounded-full border-[3px] border-fg bg-surface" aria-hidden />
                <label htmlFor="route-from" className="sr-only">
                  From
                </label>
                <input
                  id="route-from"
                  value={from}
                  onChange={(e) => setFrom(e.target.value)}
                  placeholder="Start"
                  autoComplete="off"
                  className="h-11 min-w-0 flex-1 bg-transparent text-sm font-medium text-fg placeholder:text-fg-subtle focus:outline-none"
                />
              </div>
              <div className="ml-[13px] h-2 border-l-2 border-dotted border-line-strong" aria-hidden />
              <div className="flex items-center gap-3 rounded-xl px-2 focus-within:bg-surface-2">
                <MapPin className="size-4 shrink-0 -translate-x-0.5 text-accent-ink" aria-hidden />
                <label htmlFor="route-to" className="sr-only">
                  To
                </label>
                <input
                  id="route-to"
                  value={to}
                  onChange={(e) => setTo(e.target.value)}
                  placeholder="Destination"
                  autoComplete="off"
                  className="h-11 min-w-0 flex-1 bg-transparent text-sm font-medium text-fg placeholder:text-fg-subtle focus:outline-none"
                />
              </div>
              <Button type="button" variant="secondary" size="icon-sm" onClick={swap} aria-label="Swap start and destination" className="absolute top-1/2 right-1 -translate-y-1/2 rounded-full">
                <ArrowUpDown />
              </Button>
            </div>

            {via ? (
              <div className="mx-2 mt-2 flex items-center gap-2">
                <span className="inline-flex h-7 items-center gap-1.5 rounded-full border border-line bg-surface-2 pr-1 pl-2.5 text-xs text-fg">
                  Via {viaName ?? "selected street"}
                  <button
                    type="button"
                    onClick={() => {
                      setVia(null);
                      submit({ via: null });
                    }}
                    className="rounded-full p-1 text-fg-muted hover:bg-surface-3 hover:text-fg"
                    aria-label="Remove the via street"
                  >
                    <X className="size-3" />
                  </button>
                </span>
              </div>
            ) : null}

            <div className="mt-2 flex flex-wrap items-center gap-2 border-t border-line px-2 pt-2.5 pb-0.5">
              <Clock className="size-4 text-fg-subtle" aria-hidden />
              <label htmlFor="route-depart" className="text-xs text-fg-muted">
                Depart at
              </label>
              <input
                id="route-depart"
                type="time"
                value={departAt}
                step={300}
                onChange={(e) => {
                  setDepartAt(e.target.value);
                  if (e.target.value) submit({ departAt: e.target.value });
                }}
                className="h-8 rounded-lg border border-line bg-surface-2 px-2 font-num text-sm text-fg focus-visible:border-signal/50 focus-visible:outline-none dark:[color-scheme:dark]"
              />
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  const now = formatTime(mockNow());
                  setDepartAt(now);
                  submit({ departAt: now });
                }}
              >
                Now
              </Button>
              <Button type="submit" size="sm" className="ml-auto">
                Plan
              </Button>
            </div>
          </form>
        </div>

        <div className="order-3 space-y-4 px-4 pt-5 pb-6 sm:px-6">
          {plan.error ? (
            <ErrorState error={plan.error} onRetry={plan.retry} />
          ) : !plan.data ? (
            <div className="space-y-3" aria-busy="true" aria-label="Planning routes">
              <Skeleton className="h-24 w-full rounded-2xl" />
              {[0, 1, 2].map((i) => (
                <RouteCompareCardSkeleton key={i} />
              ))}
            </div>
          ) : routes.length === 0 ? (
            <EmptyState
              title="No bikeable route found"
              body="UMI couldn't link these two places with streets riders have measured. Try a nearby street or another time."
              action={
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => {
                    setFrom(HOME);
                    setTo(WORK);
                    submit({ from: HOME, to: WORK });
                  }}
                >
                  Use my commute
                </Button>
              }
            />
          ) : (
            <>
              <CalmNudge routes={routes} selected={goal} onPick={setGoal} />
              <div className="flex items-center justify-between gap-3">
                <span className="flex items-center gap-2 text-xs text-fg-muted">
                  Prioritise
                  {updating ? <Loader2 className="size-3.5 animate-spin text-fg-subtle" aria-label="Updating routes" /> : null}
                </span>
                <Segmented
                  size="sm"
                  value={goal}
                  onChange={setGoal}
                  label="Route priority"
                  options={GOALS.map((g) => ({ value: g, label: g[0].toUpperCase() + g.slice(1) }))}
                />
              </div>
              <ol className={cn("space-y-3 transition-opacity", updating && "opacity-60")} aria-label="Route alternatives">
                {routes.map((r) => (
                  <li key={r.id}>
                    <RouteCompareCard route={r} baseline={fastest} selected={r.id === selected?.id} onSelect={() => setGoal(r.goal)} viaHighlight={viaName} />
                  </li>
                ))}
              </ol>
              <p className="flex items-start gap-2 px-1 text-[11px] leading-4 text-fg-subtle">
                <Sparkles className="mt-px size-3.5 shrink-0 text-accent-ink" aria-hidden />
                <span>
                  Scores are forecast for {request.departAt ?? "08:00"} from 30 days of rides on each street. Calmest and Cleanest are part of{" "}
                  <Link href="/app/profile#premium" className="text-accent-ink underline-offset-2 hover:underline">
                    UMI Premium
                  </Link>
                  , free during your trial.
                </span>
              </p>
            </>
          )}
        </div>
      </div>

      <div className="relative order-2 mx-4 mt-5 h-[340px] overflow-hidden rounded-2xl border border-line sm:mx-6 sm:h-[420px] lg:m-0 lg:h-auto lg:flex-1 lg:rounded-none lg:border-0">
        {routes.length && selected && !streets.loading ? (
          <RoutesMap
            routes={routes}
            selectedId={selected.id}
            onSelect={(id) => setGoal(routes.find((r) => r.id === id)?.goal ?? goal)}
            fromLabel={request.from}
            toLabel={request.to}
            streets={streets.data}
            hour={Number((request.departAt ?? "08:00").slice(0, 2)) || 0}
          />
        ) : (
          <div className="flex size-full items-center justify-center bg-[var(--map-bg)]">
            {plan.loading ? <Skeleton className="size-full rounded-none opacity-40" /> : <p className="text-sm text-fg-muted">No route to show</p>}
          </div>
        )}
      </div>
    </div>
  );
}
