"use client";

import type { ExpressionSpecification, FilterSpecification } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import { Layer, Popup, Source, type MapLayerMouseEvent, type MapRef } from "react-map-gl/maplibre";
import { BaseMap } from "@/components/map/base-map";
import { BASE_COLORS } from "@/components/map/map-style";
import { ScoreBadge } from "@/components/score/score-badge";
import { formatDay, hourLabel, plural } from "@/lib/format";
import { boundsOf } from "@/lib/geo";
import { usePrefersReducedMotion } from "@/lib/hooks/use-media-query";
import { useResolvedTheme } from "@/lib/hooks/use-resolved-theme";
import { scoreColorExpression } from "@/lib/score";
import { hourProp, scoreAt, streetsToGeoJSON } from "@/lib/street-geojson";
import type { BrakeHotspot, MapMetric, Pothole, StreetSegment } from "@/lib/types";

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
  showHotspots: boolean;
  showPotholes: boolean;
  bikeOnly: boolean;
  selectedId: string | null;
  onSelect: (id: string | null) => void;
  /** Frame a street (from a list or a deep link). */
  focus: StreetMapFocus | null;
  showControls?: boolean;
  label: string;
}

const WIDTH: ExpressionSpecification = ["interpolate", ["linear"], ["zoom"], 11, 1.6, 13, 3, 15, 6, 17, 10];
const CASING: ExpressionSpecification = ["interpolate", ["linear"], ["zoom"], 11, 3, 13, 5.5, 15, 10, 17, 15];
const HALO: ExpressionSpecification = ["interpolate", ["linear"], ["zoom"], 11, 5, 13, 8, 15, 14, 17, 19];
const ALL: FilterSpecification = ["has", "id"];
const BIKE_ONLY: FilterSpecification = ["==", ["get", "bikeLane"], true];
const FOCUS_OPTIONS = { padding: 120, maxZoom: 15 };

const SEVERITY: Record<Pothole["severity"], string> = { low: "Minor", medium: "Noticeable", high: "Severe" };

type PopupState = { kind: "hotspot"; item: BrakeHotspot } | { kind: "pothole"; item: Pothole } | null;

export default function StreetMapCanvas({
  streets,
  metric,
  hour,
  hotspots,
  potholes,
  showHotspots,
  showPotholes,
  bikeOnly,
  selectedId,
  onSelect,
  focus,
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

  const interactive = useMemo(() => ["streets", ...(showHotspots ? ["hotspots"] : []), ...(showPotholes ? ["potholes"] : [])], [showHotspots, showPotholes]);

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
    setPopup(null);
    onSelect(id);
  };

  const colors = BASE_COLORS[theme];
  const color = scoreColorExpression(["get", hourProp(metric, hour)], theme) as unknown as ExpressionSpecification;
  const filter = bikeOnly ? BIKE_ONLY : ALL;
  const hovered = hover ? byId.get(hover.id) : undefined;

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
        {popup ? (
          <Popup
            longitude={popup.item.coordinates[0]}
            latitude={popup.item.coordinates[1]}
            anchor="bottom"
            offset={popup.kind === "hotspot" ? 20 : 12}
            closeButton={false}
            onClose={() => setPopup(null)}
            maxWidth="260px"
          >
            {popup.kind === "hotspot" ? (
              <div>
                <p className="label-mono text-[10px] text-accent-ink">Hard-brake hotspot</p>
                <p className="mt-1 text-[13px] leading-5 font-semibold">{popup.item.label}</p>
                <p className="mt-1 text-xs text-fg-muted">
                  <span className="font-num font-semibold text-fg">{popup.item.hardBrakesWeek}</span> hard brakes this week · peak {hourLabel(popup.item.peakHour)}
                </p>
                <p className="text-xs text-fg-muted">
                  Avg. deceleration <span className="font-num font-semibold text-fg">{popup.item.avgDecel.toFixed(1)}</span> m/s²
                </p>
              </div>
            ) : (
              <div>
                <p className="label-mono text-[10px] text-mid">{SEVERITY[popup.item.severity]} pothole</p>
                <p className="mt-1 text-[13px] leading-5 font-semibold">{popup.item.street}</p>
                <p className="mt-1 text-xs text-fg-muted">
                  Confirmed by <span className="font-num font-semibold text-fg">{popup.item.confirmations}</span> {plural(popup.item.confirmations, "rider")} · first felt{" "}
                  {formatDay(`${popup.item.firstSeen}T12:00:00Z`, { day: "numeric", month: "short" })}
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
