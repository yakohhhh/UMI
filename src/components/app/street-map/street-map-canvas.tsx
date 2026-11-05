"use client";

import { Hourglass, Route, Users } from "lucide-react";
import type { ExpressionSpecification, FilterSpecification } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import { Layer, Popup, Source, type MapLayerMouseEvent, type MapRef } from "react-map-gl/maplibre";
import { HAZARD_META } from "@/components/app/ride-events";
import { BaseMap } from "@/components/map/base-map";
import { BASE_COLORS } from "@/components/map/map-style";
import { ScoreBadge } from "@/components/score/score-badge";
import { TIME_ZONE, formatDay, hourLabel, plural } from "@/lib/format";
import { boundsOf } from "@/lib/geo";
import { usePrefersReducedMotion } from "@/lib/hooks/use-media-query";
import { useResolvedTheme } from "@/lib/hooks/use-resolved-theme";
import { mockNow } from "@/lib/mock";
import { HAZARD_LIFETIME, MAP_MIN_RIDERS } from "@/lib/reports";
import { scoreColorExpression } from "@/lib/score";
import { hourProp, scoreAt, streetsToGeoJSON } from "@/lib/street-geojson";
import type { BrakeHotspot, CityHazard, MapMetric, Pothole, StreetSegment } from "@/lib/types";

export interface StreetMapFocus {
  id: string;
  /** Changes every time the same street should be framed again. */
  nonce: number;
}

export interface StreetMapCanvasProps {
  streets: StreetSegment[];
  metric: MapMetric;
  hour: number;
  hotspots: BrakeHotspot[];
  potholes: Pothole[];
  /** Live rider flags (3+ different riders, not fixed). */
  flags: CityHazard[];
  /** Flags the rider's Calmest commute stays clear of while another option passes them. */
  calmestAvoids: ReadonlySet<string>;
  showHotspots: boolean;
  showPotholes: boolean;
  showFlags: boolean;
  bikeOnly: boolean;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  /** Frame a street (from a list or a deep link). */
  focus: StreetMapFocus | null;
  /** Fly to a flag and open its popup (from the keyboard list in the legend). */
  flagFocus: StreetMapFocus | null;
  showControls?: boolean;
  label: string;
}

const WIDTH: ExpressionSpecification = ["interpolate", ["linear"], ["zoom"], 11, 1.6, 13, 3, 15, 6, 17, 10];
const CASING: ExpressionSpecification = ["interpolate", ["linear"], ["zoom"], 11, 3, 13, 5.5, 15, 10, 17, 15];
const HALO: ExpressionSpecification = ["interpolate", ["linear"], ["zoom"], 11, 5, 13, 8, 15, 14, 17, 19];
const ALL: FilterSpecification = ["has", "id"];
const BIKE_ONLY: FilterSpecification = ["==", ["get", "bikeLane"], true];
const FOCUS_OPTIONS = { padding: 120, maxZoom: 15 };
const FLAG_STROKE = "#0b1220";

const SEVERITY: Record<Pothole["severity"], string> = { low: "Minor", medium: "Noticeable", high: "Severe" };

type PopupState = { kind: "hotspot"; item: BrakeHotspot } | { kind: "pothole"; item: Pothole } | { kind: "flag"; item: CityHazard } | null;

const madridDay = (d: Date) => new Intl.DateTimeFormat("en-CA", { timeZone: TIME_ZONE }).format(d);

/** "today", "yesterday" or "15 Oct" for a YYYY-MM-DD day. */
function sinceDay(day: string) {
  const now = mockNow();
  if (day === madridDay(now)) return "today";
  if (day === madridDay(new Date(now.getTime() - 86_400_000))) return "yesterday";
  return formatDay(`${day}T12:00:00Z`, { day: "numeric", month: "short" });
}

function FlagPopup({ item, avoided }: { item: CityHazard; avoided: boolean }) {
  const meta = HAZARD_META[item.kind];
  const Icon = meta.icon;
  const lifetime = HAZARD_LIFETIME[item.kind];
  return (
    <div>
      <p className="flex items-center gap-1.5">
        <span className="flex size-5 shrink-0 items-center justify-center rounded-full ring-[1.5px] ring-asphalt-900" style={{ backgroundColor: meta.color }} aria-hidden>
          <Icon className="size-3 text-asphalt-900" />
        </span>
        <span className="label-mono text-[10px] text-fg">{meta.label}</span>
      </p>
      <p className="mt-1.5 text-[13px] leading-5 font-semibold">{item.street}</p>
      <p className="mt-0.5 text-xs text-fg-muted">
        <span className="font-num font-semibold text-fg">{item.riders}</span> {plural(item.riders, "rider")} · first flagged {sinceDay(item.firstSeen)}
      </p>
      <p className="mt-2 flex gap-1.5 text-xs text-fg-muted">
        <Hourglass className="mt-0.5 size-3 shrink-0" aria-hidden />
        <span>
          <span className="sr-only">Stays live: </span>
          {lifetime.charAt(0).toUpperCase() + lifetime.slice(1)}
        </span>
      </p>
      {avoided ? (
        <p className="mt-1 flex gap-1.5 text-xs font-medium text-accent-ink">
          <Route className="mt-0.5 size-3 shrink-0" aria-hidden />
          Your Calmest route avoids it
        </p>
      ) : (
        <p className="mt-1 flex gap-1.5 text-xs text-fg-subtle">
          <Users className="mt-0.5 size-3 shrink-0" aria-hidden />
          Verified by {MAP_MIN_RIDERS}+ riders · the warning is free for everyone
        </p>
      )}
    </div>
  );
}

export default function StreetMapCanvas({
  streets,
  metric,
  hour,
  hotspots,
  potholes,
  flags,
  calmestAvoids,
  showHotspots,
  showPotholes,
  showFlags,
  bikeOnly,
  selectedId,
  onSelect,
  focus,
  flagFocus,
  showControls = true,
  label,
}: StreetMapCanvasProps) {
  const theme = useResolvedTheme();
  const reduceMotion = usePrefersReducedMotion();
  const mapRef = useRef<MapRef>(null);
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);
  const [pointer, setPointer] = useState(false);
  const [popup, setPopup] = useState<PopupState>(null);

  const data = useMemo(() => streetsToGeoJSON(streets), [streets]);
  const byId = useMemo(() => new Map(streets.map((s) => [s.id, s])), [streets]);
  const hotspotData = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: hotspots.map((h) => ({ type: "Feature" as const, properties: { id: h.id, count: h.hardBrakesWeek }, geometry: { type: "Point" as const, coordinates: h.coordinates } })),
    }),
    [hotspots],
  );
  const potholeData = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: potholes.map((p) => ({ type: "Feature" as const, properties: { id: p.id, n: p.confirmations }, geometry: { type: "Point" as const, coordinates: p.coordinates } })),
    }),
    [potholes],
  );
  const flagData = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: flags.map((h) => ({ type: "Feature" as const, properties: { id: h.id, color: HAZARD_META[h.kind].color }, geometry: { type: "Point" as const, coordinates: h.coordinates } })),
    }),
    [flags],
  );

  // Deep links open the map already framed on the street.
  const initialView = useRef(
    (() => {
      const s = focus ? byId.get(focus.id) : undefined;
      return s ? { bounds: boundsOf(s.coordinates), fitBoundsOptions: FOCUS_OPTIONS } : { longitude: 2.172, latitude: 41.3965, zoom: 13.4 };
    })(),
  );
  const firstFocus = useRef(focus?.nonce);

  useEffect(() => {
    if (!focus || focus.nonce === firstFocus.current) return;
    const s = byId.get(focus.id);
    const map = mapRef.current;
    if (!s || !map) return;
    map.fitBounds(boundsOf(s.coordinates), { ...FOCUS_OPTIONS, duration: reduceMotion ? 0 : 900 });
  }, [focus, byId, reduceMotion]);

  const handledFlag = useRef<number | undefined>(undefined);
  useEffect(() => {
    if (!flagFocus || flagFocus.nonce === handledFlag.current) return;
    const item = flags.find((h) => h.id === flagFocus.id);
    const map = mapRef.current;
    if (!item || !map) return;
    handledFlag.current = flagFocus.nonce;
    map.easeTo({ center: item.coordinates, zoom: Math.max(map.getZoom(), 15), duration: reduceMotion ? 0 : 900 });
    setPopup({ kind: "flag", item });
  }, [flagFocus, flags, reduceMotion]);

  const interactive = useMemo(
    () => ["streets", ...(showHotspots ? ["hotspots"] : []), ...(showPotholes ? ["potholes"] : []), ...(showFlags ? ["flags-hit", "flags"] : [])],
    [showHotspots, showPotholes, showFlags],
  );

  const onMove = (e: MapLayerMouseEvent) => {
    const f = e.features?.[0];
    setPointer(Boolean(f));
    if (f && f.layer.id === "streets") setHover({ id: String(f.properties?.id), x: e.point.x, y: e.point.y });
    else setHover(null);
  };

  const onClick = (e: MapLayerMouseEvent) => {
    const f = e.features?.[0];
    if (!f) {
      setPopup(null);
      onSelect(null);
      return;
    }
    const id = String(f.properties?.id);
    if (f.layer.id === "hotspots") {
      const item = hotspots.find((h) => h.id === id);
      setPopup(item ? { kind: "hotspot", item } : null);
      return;
    }
    if (f.layer.id === "potholes") {
      const item = potholes.find((p) => p.id === id);
      setPopup(item ? { kind: "pothole", item } : null);
      return;
    }
    if (f.layer.id === "flags" || f.layer.id === "flags-hit") {
      const item = flags.find((h) => h.id === id);
      setPopup(item ? { kind: "flag", item } : null);
      return;
    }
    setPopup(null);
    onSelect(id);
  };

  const colors = BASE_COLORS[theme];
  const color = scoreColorExpression(["get", hourProp(metric, hour)], theme) as unknown as ExpressionSpecification;
  const filter = bikeOnly ? BIKE_ONLY : ALL;
  const hovered = hover ? byId.get(hover.id) : undefined;
  // a popup closes with its layer (and stays closed when the layer comes back)
  const layerOn = { hotspot: showHotspots, pothole: showPotholes, flag: showFlags };
  const openPopup = popup && layerOn[popup.kind] ? popup : null;
  useEffect(() => {
    setPopup((p) => (p && !{ hotspot: showHotspots, pothole: showPotholes, flag: showFlags }[p.kind] ? null : p));
  }, [showHotspots, showPotholes, showFlags]);

  return (
    <div className="relative size-full">
      <BaseMap
        ref={mapRef}
        label={label}
        initialViewState={initialView.current}
        className="size-full"
        showControls={showControls}
        interactiveLayerIds={interactive}
        cursor={pointer ? "pointer" : "grab"}
        onMouseMove={onMove}
        onMouseLeave={() => {
          setHover(null);
          setPointer(false);
        }}
        onClick={onClick}
      >
        <Source id="streets" type="geojson" data={data} promoteId="id">
          <Layer id="streets-casing" type="line" filter={filter} layout={{ "line-cap": "round", "line-join": "round" }} paint={{ "line-color": colors.casing, "line-width": CASING, "line-opacity": 0.85 }} />
          <Layer
            id="streets-halo"
            type="line"
            filter={["in", ["get", "id"], ["literal", [hover?.id ?? "", selectedId ?? ""]]]}
            layout={{ "line-cap": "round", "line-join": "round" }}
            paint={{ "line-color": theme === "dark" ? "#ffffff" : "#0b1220", "line-width": HALO, "line-opacity": 0.92 }}
          />
          <Layer id="streets" type="line" filter={filter} layout={{ "line-cap": "round", "line-join": "round" }} paint={{ "line-color": color, "line-width": WIDTH }} />
        </Source>
        {showPotholes ? (
          <Source id="potholes" type="geojson" data={potholeData}>
            <Layer
              id="potholes"
              type="circle"
              paint={{
                "circle-radius": ["interpolate", ["linear"], ["zoom"], 12, 3.5, 16, 8],
                "circle-color": "#f5c542",
                "circle-stroke-color": colors.casing,
                "circle-stroke-width": 2,
              }}
            />
          </Source>
        ) : null}
        {showHotspots ? (
          <Source id="hotspots" type="geojson" data={hotspotData}>
            <Layer
              id="hotspots"
              type="circle"
              paint={{
                "circle-radius": ["interpolate", ["linear"], ["get", "count"], 4, 7, 40, 24],
                "circle-color": "#ff5b1f",
                "circle-opacity": 0.22,
                "circle-stroke-color": "#ff5b1f",
                "circle-stroke-width": 1.5,
              }}
            />
            <Layer id="hotspots-core" type="circle" paint={{ "circle-radius": 2.5, "circle-color": theme === "dark" ? "#ffffff" : "#0b1220" }} />
          </Source>
        ) : null}
        {showFlags ? (
          <Source id="flags" type="geojson" data={flagData}>
            {/* invisible, wider hit area: a slightly-off tap should open the flag, not the street underneath */}
            <Layer id="flags-hit" type="circle" paint={{ "circle-radius": 16, "circle-opacity": 0 }} />
            <Layer
              id="flags"
              type="circle"
              paint={{
                "circle-radius": ["interpolate", ["linear"], ["zoom"], 12, 5, 16, 10],
                "circle-color": ["get", "color"],
                "circle-stroke-color": FLAG_STROKE,
                "circle-stroke-width": 2,
              }}
            />
            {/* the dark core tells a rider flag apart from a measured pothole of the same colour */}
            <Layer id="flags-core" type="circle" paint={{ "circle-radius": ["interpolate", ["linear"], ["zoom"], 12, 1.5, 16, 3], "circle-color": FLAG_STROKE }} />
          </Source>
        ) : null}
        {openPopup ? (
          <Popup
            longitude={openPopup.item.coordinates[0]}
            latitude={openPopup.item.coordinates[1]}
            anchor="bottom"
            offset={openPopup.kind === "hotspot" ? 20 : openPopup.kind === "flag" ? 14 : 12}
            closeButton={false}
            // the map's own click handler opens, swaps and closes popups; letting the popup close itself too raced with it
            closeOnClick={false}
            onClose={() => setPopup(null)}
            maxWidth="260px"
          >
            {openPopup.kind === "flag" ? (
              <FlagPopup item={openPopup.item} avoided={calmestAvoids.has(openPopup.item.id)} />
            ) : openPopup.kind === "hotspot" ? (
              <div>
                <p className="label-mono text-[10px] text-accent-ink">Hard-brake hotspot</p>
                <p className="mt-1 text-[13px] leading-5 font-semibold">{openPopup.item.label}</p>
                <p className="mt-1 text-xs text-fg-muted">
                  <span className="font-num font-semibold text-fg">{openPopup.item.hardBrakesWeek}</span> hard brakes this week · peak {hourLabel(openPopup.item.peakHour)}
                </p>
                <p className="text-xs text-fg-muted">
                  Avg. deceleration <span className="font-num font-semibold text-fg">{openPopup.item.avgDecel.toFixed(1)}</span> m/s²
                </p>
              </div>
            ) : (
              <div>
                <p className="label-mono text-[10px] text-mid">{SEVERITY[openPopup.item.severity]} pothole</p>
                <p className="mt-1 text-[13px] leading-5 font-semibold">{openPopup.item.street}</p>
                <p className="mt-1 text-xs text-fg-muted">
                  Confirmed by <span className="font-num font-semibold text-fg">{openPopup.item.confirmations}</span> {plural(openPopup.item.confirmations, "rider")} · first felt{" "}
                  {formatDay(`${openPopup.item.firstSeen}T12:00:00Z`, { day: "numeric", month: "short" })}
                </p>
              </div>
            )}
          </Popup>
        ) : null}
      </BaseMap>
      {hover && hovered ? (
        <div
          className="pointer-events-none absolute top-0 left-0 z-10 hidden max-w-64 rounded-xl border border-line bg-surface/95 px-3 py-2 shadow-[var(--shadow-lift)] backdrop-blur md:block"
          style={{ transform: `translate(${hover.x}px, ${hover.y}px) translate(-50%, calc(-100% - 14px))` }}
          aria-hidden
        >
          <div className="flex items-center gap-2">
            <span className="truncate text-[13px] font-semibold text-fg">{hovered.name}</span>
            <ScoreBadge metric={metric} score={scoreAt(hovered, metric, hour)} size="sm" showIcon={false} />
          </div>
          {hovered.from || hovered.to ? <p className="truncate text-[11px] text-fg-muted">{[hovered.from, hovered.to].filter(Boolean).join(" → ")}</p> : null}
        </div>
      ) : null}
    </div>
  );
}
