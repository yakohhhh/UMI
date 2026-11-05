"use client";

import { motion } from "framer-motion";
import { ChevronUp, Layers, List, X } from "lucide-react";
import dynamic from "next/dynamic";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useId, useMemo, useRef, useState, type ReactNode } from "react";
import { HAZARD_META } from "@/components/app/ride-events";
import { HourSlider } from "@/components/data/hour-slider";
import { EmptyState, ErrorState } from "@/components/data/states";
import { DimensionIcon } from "@/components/score/dimension-icon";
import { ScoreLegend } from "@/components/score/score-badge";
import { ScoreRing } from "@/components/score/score-gauge";
import { Button } from "@/components/ui/button";
import { Popover, PopoverClose, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Segmented, type SegmentedOption } from "@/components/ui/segmented";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { getBrakeHotspots, getLiveHazards, getPotholes, getStreetSegments, planRoutes, type RouteRequest } from "@/lib/api";
import { hourLabel, plural } from "@/lib/format";
import { distanceToLine } from "@/lib/geo";
import { useApi } from "@/lib/hooks/use-api";
import { useMediaQuery } from "@/lib/hooks/use-media-query";
import { MAP_MIN_RIDERS } from "@/lib/reports";
import { DIMENSIONS, bandLabel } from "@/lib/score";
import { scoreAt } from "@/lib/street-geojson";
import type { CityHazard, HazardKind, MapMetric, PlannedRoute } from "@/lib/types";
import { cn } from "@/lib/utils";
import type { StreetMapFocus } from "./street-map-canvas";
import { CityAtHour, ShareBar, StreetDetails, bandShares, streetSpan } from "./street-panel";

const StreetMapCanvas = dynamic(() => import("./street-map-canvas"), {
  ssr: false,
  loading: () => <MapLoading />,
});

const METRICS: MapMetric[] = ["overall", "comfort", "safety", "air", "noise"];
const NO_FLAGS: CityHazard[] = [];
/** One kind per map colour, for the layer swatch. */
const SWATCH_KINDS: HazardKind[] = ["roadworks", "blocked_lane", "danger"];

/** The rider's saved commute (the route planner's default trip). */
const COMMUTE: RouteRequest = { from: "Plaça de la Vila de Gràcia", to: "Carrer de Pallars, 22@", departAt: "08:00" };
// route lines are simplified, so "on it" and "clear of it" both leave room
const ON_ROUTE_M = 60;
const CLEAR_OF_ROUTE_M = 150;

interface LayerState {
  bikeOnly: boolean;
  hotspots: boolean;
  potholes: boolean;
  flags: boolean;
}

const LAYER_ROWS: { key: keyof LayerState; label: string; hint: string; swatch: ReactNode }[] = [
  {
    key: "bikeOnly",
    label: "Bike lanes only",
    hint: "Hide streets without a protected lane",
    swatch: <span className="h-1.5 w-4 rounded-full bg-lane" />,
  },
  {
    key: "hotspots",
    label: "Hard-brake hotspots",
    hint: "Junctions where riders brake above 3 m/s²",
    swatch: <span className="size-3.5 rounded-full border-[1.5px] border-signal bg-signal/25" />,
  },
  {
    key: "potholes",
    label: "Potholes",
    hint: "Impacts confirmed by at least 3 riders",
    swatch: <span className="size-2.5 rounded-full bg-score-mid ring-2 ring-surface" />,
  },
  {
    key: "flags",
    label: "Rider flags",
    hint: `Flagged from riders' Clips · verified by ${MAP_MIN_RIDERS}+ riders`,
    swatch: <FlagSwatch />,
  },
];

/** Flags another commute option passes while the Calmest one stays clear: the only case where "avoids it" is honest. */
function calmestAvoids(flags: CityHazard[], routes: PlannedRoute[]): ReadonlySet<string> {
  const calm = routes.find((r) => r.goal === "calmest");
  if (!calm) return new Set();
  const others = routes.filter((r) => r !== calm);
  return new Set(
    flags
      .filter((h) => distanceToLine(h.coordinates, calm.coordinates) >= CLEAR_OF_ROUTE_M && others.some((r) => distanceToLine(h.coordinates, r.coordinates) <= ON_ROUTE_M))
      .map((h) => h.id),
  );
}

function parseMetric(v: string | null): MapMetric | null {
  return v && (METRICS as string[]).includes(v) ? (v as MapMetric) : null;
}
function parseHour(v: string | null) {
  const n = v === null ? NaN : Number(v);
  return Number.isInteger(n) && n >= 0 && n <= 23 ? n : null;
}

function MapLoading() {
  return (
    <div className="relative size-full bg-[var(--map-bg)]" aria-busy="true" aria-label="Loading the street map">
      <Skeleton className="absolute inset-0 rounded-none opacity-40" />
      <div className="absolute inset-0 flex items-center justify-center">
        <span className="rounded-full border border-line bg-surface/90 px-3 py-1.5 text-xs text-fg-muted shadow-[var(--shadow-soft)]">Loading streets…</span>
      </div>
    </div>
  );
}

function FlagSwatch() {
  return (
    <span className="flex -space-x-0.5" aria-hidden>
      {SWATCH_KINDS.map((k) => (
        <span key={k} className="size-2 rounded-full ring-[1.5px] ring-asphalt-900" style={{ backgroundColor: HAZARD_META[k].color }} />
      ))}
    </span>
  );
}

function HazardDot({ kind }: { kind: HazardKind }) {
  const { icon: Icon, color } = HAZARD_META[kind];
  return (
    <span className="flex size-6 shrink-0 items-center justify-center rounded-full ring-[1.5px] ring-asphalt-900" style={{ backgroundColor: color }} aria-hidden>
      <Icon className="size-3.5 text-asphalt-900" />
    </span>
  );
}

/** Legend chip that doubles as the keyboard way into the flags: each row frames the flag and opens its popup. */
function FlagLegend({ flags, onPick }: { flags: CityHazard[] | undefined; onPick: (id: string) => void }) {
  if (!flags?.length) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-fg-muted">
        <FlagSwatch /> {flags ? "No rider flags live" : "Rider flags"}
      </span>
    );
  }
  const sorted = [...flags].sort((a, b) => b.riders - a.riders);
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button type="button" className="-mx-2 -my-2 inline-flex min-h-8 items-center gap-1.5 rounded-full px-2 text-xs text-fg-muted transition-colors hover:text-fg focus-visible:ring-2 focus-visible:ring-signal/50 focus-visible:outline-none" aria-label={`Rider flags, ${flags.length} live: show the list`}>
          <FlagSwatch /> Rider flags <span className="font-num font-semibold text-fg">{flags.length}</span>
          <ChevronUp className="size-3" aria-hidden />
        </button>
      </PopoverTrigger>
      <PopoverContent side="top" align="start" collisionPadding={16} className="w-80 max-w-[calc(100vw-2rem)] p-2">
        <p className="label-mono px-2 pt-1 text-[10px] text-fg-subtle">Live rider flags</p>
        <p className="px-2 pt-0.5 pb-2 text-xs text-fg-muted">Verified by {MAP_MIN_RIDERS}+ riders · pick one to see it on the map</p>
        <ul className="max-h-72 space-y-0.5 overflow-y-auto">
          {sorted.map((h) => (
            <li key={h.id}>
              <PopoverClose asChild>
                <button type="button" onClick={() => onPick(h.id)} className="flex w-full items-center gap-3 rounded-xl px-2 py-2 text-left hover:bg-surface-2">
                  <HazardDot kind={h.kind} />
                  <span className="min-w-0 flex-1">
                    <span className="block text-sm font-medium text-fg">{HAZARD_META[h.kind].label}</span>
                    <span className="block truncate text-xs text-fg-muted">{h.street}</span>
                  </span>
                  <span className="shrink-0 text-xs text-fg-muted">
                    <span className="font-num font-semibold text-fg">{h.riders}</span> {plural(h.riders, "rider")}
                  </span>
                </button>
              </PopoverClose>
            </li>
          ))}
        </ul>
        <p className="mt-1 border-t border-line px-2 pt-2 pb-1 text-xs text-fg-subtle">Spotted one? Press the button on your Clip · hold it to say what it is.</p>
      </PopoverContent>
    </Popover>
  );
}

function LayersMenu({ layers, onChange, compact }: { layers: LayerState; onChange: (l: LayerState) => void; compact?: boolean }) {
  const id = useId();
  const active = Object.values(layers).filter(Boolean).length;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant={compact ? "secondary" : "ghost"} size={compact ? "icon" : "sm"} className="relative" aria-label={compact ? `Map layers${active ? `, ${active} on` : ""}` : undefined}>
          <Layers />
          {!compact ? "Layers" : null}
          {active ? (
            <span className={cn("flex size-4 items-center justify-center rounded-full bg-signal font-num text-[10px] font-semibold text-asphalt-900", compact && "absolute -top-1 -right-1")} aria-hidden={compact}>
              {active}
            </span>
          ) : null}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 p-2">
        <p className="label-mono px-2 pt-1 pb-2 text-[10px] text-fg-subtle">Map layers</p>
        <ul className="space-y-0.5">
          {LAYER_ROWS.map((row) => (
            <li key={row.key} className="flex items-center gap-3 rounded-xl px-2 py-2 hover:bg-surface-2">
              <span className="flex w-5 shrink-0 justify-center" aria-hidden>
                {row.swatch}
              </span>
              <label htmlFor={`${id}-${row.key}`} className="min-w-0 flex-1 cursor-pointer">
                <span className="block text-sm font-medium text-fg">{row.label}</span>
                <span className="block text-xs text-fg-muted">{row.hint}</span>
              </label>
              <Switch id={`${id}-${row.key}`} checked={layers[row.key]} onCheckedChange={(v) => onChange({ ...layers, [row.key]: v })} />
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}

function MapLegend({
  metric,
  layers,
  flags,
  onPickFlag,
  className,
}: {
  metric: MapMetric;
  layers: LayerState;
  flags: CityHazard[] | undefined;
  onPickFlag: (id: string) => void;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-center gap-x-4 gap-y-1.5", className)}>
      <ScoreLegend metric={metric} compact />
      {layers.hotspots ? (
        <span className="inline-flex items-center gap-1.5 text-xs text-fg-muted">
          <span className="size-3 rounded-full border-[1.5px] border-signal bg-signal/25" aria-hidden /> Hotspot
        </span>
      ) : null}
      {layers.potholes ? (
        <span className="inline-flex items-center gap-1.5 text-xs text-fg-muted">
          <span className="size-2.5 rounded-full bg-score-mid" aria-hidden /> Pothole
        </span>
      ) : null}
      {layers.flags ? <FlagLegend flags={flags} onPick={onPickFlag} /> : null}
    </div>
  );
}

export function StreetMapView() {
  const params = useSearchParams();
  const streets = useApi(getStreetSegments);
  const hotspots = useApi(getBrakeHotspots);
  const potholes = useApi(getPotholes);
  const hazards = useApi(getLiveHazards);
  const commute = useApi(() => planRoutes(COMMUTE));
  const isDesktop = useMediaQuery("(min-width: 1024px)", true);

  const initialStreet = params.get("street");
  const [metric, setMetric] = useState<MapMetric>(() => parseMetric(params.get("metric")) ?? "overall");
  const [hour, setHour] = useState(() => parseHour(params.get("hour")) ?? 8);
  const [selectedId, setSelectedId] = useState<string | null>(initialStreet);
  const [focus, setFocus] = useState<StreetMapFocus | null>(initialStreet ? { id: initialStreet, nonce: 0 } : null);
  const [layers, setLayers] = useState<LayerState>({ bikeOnly: false, hotspots: false, potholes: false, flags: true });
  const [flagFocus, setFlagFocus] = useState<StreetMapFocus | null>(null);
  const [query, setQuery] = useState(params.get("q") ?? "");
  const [sheetOpen, setSheetOpen] = useState(false);
  const [sheetKind, setSheetKind] = useState<"details" | "explore">("explore");
  const panelRef = useRef<HTMLElement>(null);

  // The top-bar search lands here with ?q=…
  const q = params.get("q");
  useEffect(() => {
    if (q === null) return;
    setQuery(q);
    setSelectedId(null);
    if (!window.matchMedia("(min-width: 1024px)").matches) {
      setSheetKind("explore");
      setSheetOpen(true);
    }
  }, [q]);

  useEffect(() => {
    panelRef.current?.scrollTo({ top: 0 });
  }, [selectedId]);

  const data = streets.data;
  const selected = useMemo(() => (data && selectedId ? (data.find((s) => s.id === selectedId) ?? null) : null), [data, selectedId]);
  const shares = useMemo(() => (data?.length ? bandShares(data, metric, hour) : null), [data, metric, hour]);
  const avoided = useMemo(() => calmestAvoids(hazards.data ?? NO_FLAGS, commute.data ?? []), [hazards.data, commute.data]);

  const pick = useCallback((id: string) => {
    setSelectedId(id);
    setFocus({ id, nonce: Date.now() });
    setSheetOpen(false);
  }, []);

  const pickFlag = useCallback((id: string) => setFlagFocus({ id, nonce: Date.now() }), []);

  const openSheet = (kind: "details" | "explore") => {
    setSheetKind(kind);
    setSheetOpen(true);
  };

  const metricOptions: SegmentedOption<MapMetric>[] = METRICS.map((m) => ({
    value: m,
    icon: <DimensionIcon metric={m} className="max-sm:hidden" />,
    label: <span className="lg:max-xl:sr-only">{DIMENSIONS[m].label}</span>,
  }));

  const meta = DIMENSIONS[metric];
  const mapLabel = `Map of Barcelona streets coloured by ${meta.label.toLowerCase()} score at ${hourLabel(hour)}. Use the street list for a keyboard-accessible version.${layers.flags && hazards.data?.length ? " Rider flags are listed in the map legend." : ""}`;

  let mapArea: ReactNode;
  if (streets.error) {
    mapArea = (
      <div className="flex size-full items-center justify-center bg-[var(--map-bg)] p-6">
        <ErrorState error={streets.error} onRetry={streets.retry} className="max-w-md bg-surface" />
      </div>
    );
  } else if (!data) {
    mapArea = <MapLoading />;
  } else {
    mapArea = (
      <>
        <StreetMapCanvas
          streets={data}
          metric={metric}
          hour={hour}
          hotspots={hotspots.data ?? []}
          potholes={potholes.data ?? []}
          flags={hazards.data ?? NO_FLAGS}
          calmestAvoids={avoided}
          showHotspots={layers.hotspots}
          showPotholes={layers.potholes}
          showFlags={layers.flags}
          bikeOnly={layers.bikeOnly}
          selectedId={selectedId}
          onSelect={setSelectedId}
          focus={focus}
          flagFocus={flagFocus}
          showControls={isDesktop}
          label={mapLabel}
        />
        {data.length === 0 ? (
          <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-6">
            <EmptyState
              className="pointer-events-auto max-w-sm border-solid bg-surface/95 backdrop-blur"
              title="No streets mapped here yet"
              body="A street gets a score once 5 riders with a Clip have passed. Ride with yours to start mapping your neighbourhood."
            />
          </div>
        ) : null}
      </>
    );
  }

  return (
    <div className="flex h-[calc(100dvh-8rem-2px-env(safe-area-inset-bottom))] flex-col lg:h-[calc(100dvh-4rem-1px)] lg:flex-row">
      <h1 className="sr-only">Street map</h1>

      {/* Mobile: metric switcher above the map */}
      <div className="flex items-center gap-2 border-b border-line bg-bg px-4 py-2 lg:hidden">
        <div className="scrollbar-none -my-1 min-w-0 flex-1 overflow-x-auto py-1">
          <Segmented size="sm" value={metric} onChange={setMetric} options={metricOptions} label="Score shown on the map" />
        </div>
        <LayersMenu layers={layers} onChange={setLayers} compact />
      </div>

      <div className="relative min-h-0 flex-1">
        {mapArea}

        {/* Desktop: floating controls */}
        <div className="pointer-events-none absolute top-4 left-4 hidden lg:block">
          <div className="pointer-events-auto flex items-center gap-1 rounded-2xl border border-line bg-surface/90 p-1.5 shadow-[var(--shadow-lift)] backdrop-blur-xl">
            <Segmented value={metric} onChange={setMetric} options={metricOptions} label="Score shown on the map" />
            <span className="mx-1 h-6 w-px bg-line" aria-hidden />
            <LayersMenu layers={layers} onChange={setLayers} />
          </div>
        </div>
        <div className="pointer-events-none absolute bottom-4 left-4 hidden lg:block">
          <div className="pointer-events-auto w-[400px] rounded-2xl border border-line bg-surface/90 p-4 shadow-[var(--shadow-lift)] backdrop-blur-xl">
            <HourSlider value={hour} onChange={setHour} />
            <MapLegend metric={metric} layers={layers} flags={hazards.data} onPickFlag={pickFlag} className="mt-3 border-t border-line pt-3" />
          </div>
        </div>
      </div>

      {/* Mobile: time + selection bar under the map */}
      <div className="border-t border-line bg-bg px-4 pt-3 pb-3 lg:hidden">
        {selected ? (
          <div className="flex items-center gap-3">
            <ScoreRing score={scoreAt(selected, metric, hour)} size={44} label={`${meta.label} ${scoreAt(selected, metric, hour)}, ${bandLabel(scoreAt(selected, metric, hour), metric)}`} />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-semibold text-fg">{selected.name}</p>
              <p className="truncate text-xs text-fg-muted">{streetSpan(selected) || selected.district}</p>
            </div>
            <Button size="sm" onClick={() => openSheet("details")}>
              Details
            </Button>
            <Button variant="ghost" size="icon-sm" onClick={() => setSelectedId(null)} aria-label="Clear selected street">
              <X />
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-3">
            <div className="min-w-0 flex-1">
              {shares ? (
                <>
                  <p className="text-sm text-fg">
                    <span className="font-num font-semibold">{shares.pct.good}%</span> {meta.bands.good.toLowerCase()} at {hourLabel(hour)}
                  </p>
                  <ShareBar shares={shares} className="mt-1.5 h-1.5" />
                </>
              ) : data ? (
                <p className="text-sm text-fg-muted">No streets scored yet</p>
              ) : (
                <Skeleton className="h-8 w-40" />
              )}
            </div>
            <Button variant="secondary" size="sm" onClick={() => openSheet("explore")} disabled={!data?.length}>
              <List /> Streets
            </Button>
          </div>
        )}
        <HourSlider value={hour} onChange={setHour} compact className="mt-3" />
        {!selected ? <MapLegend metric={metric} layers={layers} flags={hazards.data} onPickFlag={pickFlag} className="mt-2.5" /> : null}
      </div>

      {/* Desktop: side panel */}
      <aside ref={panelRef} className="hidden w-[360px] shrink-0 overflow-y-auto border-l border-line bg-bg-elevated lg:block xl:w-[400px]" aria-label={selected ? `${selected.name} details` : "Streets at this hour"}>
        <div className="p-5">
          {data ? (
            <motion.div key={selected?.id ?? "overview"} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.28, ease: [0.16, 1, 0.3, 1] }}>
              {selected ? (
                <StreetDetails street={selected} metric={metric} hour={hour} onHourChange={setHour} onMetricChange={setMetric} onClose={() => setSelectedId(null)} />
              ) : data.length === 0 ? (
                <div className="pt-6 text-sm text-fg-muted">
                  <p className="font-display text-lg font-semibold text-fg">Nothing to rank yet</p>
                  <p className="mt-1.5">Calmest and most stressful streets appear here once riders have measured them.</p>
                </div>
              ) : (
                <CityAtHour streets={data} metric={metric} hour={hour} query={query} onQueryChange={setQuery} onPick={pick} />
              )}
            </motion.div>
          ) : streets.error ? null : (
            <div className="space-y-4" aria-hidden>
              <Skeleton className="h-3 w-40" />
              <Skeleton className="h-14 w-full" />
              <Skeleton className="h-2 w-full" />
              <Skeleton className="h-10 w-full" />
              {Array.from({ length: 6 }, (_, i) => (
                <Skeleton key={i} className="h-11 w-full" />
              ))}
            </div>
          )}
        </div>
      </aside>

      {/* Mobile: drawers */}
      <Sheet open={sheetOpen && !isDesktop} onOpenChange={setSheetOpen}>
        {sheetKind === "details" && selected ? (
          <SheetContent title={selected.name} hideHeader>
            <StreetDetails street={selected} metric={metric} hour={hour} onHourChange={setHour} onMetricChange={setMetric} />
          </SheetContent>
        ) : data ? (
          <SheetContent title={`Streets at ${hourLabel(hour)}`} description={`${meta.label} score · typical weekday`}>
            <CityAtHour streets={data} metric={metric} hour={hour} query={query} onQueryChange={setQuery} onPick={pick} hideSummary />
          </SheetContent>
        ) : null}
      </Sheet>
    </div>
  );
}
