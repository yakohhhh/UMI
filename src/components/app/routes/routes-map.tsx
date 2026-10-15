"use client";

import type { ExpressionSpecification } from "maplibre-gl";
import { useEffect, useMemo, useRef } from "react";
import { Layer, Marker, Source, type MapRef } from "react-map-gl/maplibre";
import { BaseMap } from "@/components/map/base-map";
import { BASE_COLORS } from "@/components/map/map-style";
import { bbox, distance, distanceToLine, pointAlong } from "@/lib/geo";
import { usePrefersReducedMotion } from "@/lib/hooks/use-media-query";
import { useResolvedTheme } from "@/lib/hooks/use-resolved-theme";
import { scoreColorExpression } from "@/lib/score";
import { hourProp, streetsToGeoJSON } from "@/lib/street-geojson";
import type { LngLat, PlannedRoute, StreetSegment } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Where to pin each route's "Calmest · 21 min" chip: the point of the route
 * furthest from the other routes and from chips already placed.
 */
function placeLabels(routes: PlannedRoute[], selectedId: string) {
  const order = [...routes].sort((a, b) => Number(b.id === selectedId) - Number(a.id === selectedId));
  const placed: LngLat[] = [];
  const out = new Map<string, LngLat>();
  for (const r of order) {
    const others = routes.filter((o) => o.id !== r.id);
    let best: LngLat = pointAlong(r.coordinates, 0.6);
    let bestScore = -Infinity;
    for (let t = 0.2; t <= 0.86; t += 0.02) {
      const p = pointAlong(r.coordinates, t);
      const fromLines = Math.min(...others.map((o) => distanceToLine(p, o.coordinates)));
      const fromChips = placed.length ? Math.min(...placed.map((q) => distance(p, q))) : Infinity;
      const score = Math.min(fromLines, fromChips * 0.7) - Math.abs(t - 0.55) * 60;
      if (score > bestScore) {
        bestScore = score;
        best = p;
      }
    }
    placed.push(best);
    out.set(r.id, best);
  }
  return out;
}
const WIDTH: ExpressionSpecification = ["interpolate", ["linear"], ["zoom"], 12, 3.5, 15, 6.5];
const WIDTH_SELECTED: ExpressionSpecification = ["interpolate", ["linear"], ["zoom"], 12, 5, 15, 9];
const CASING: ExpressionSpecification = ["interpolate", ["linear"], ["zoom"], 12, 7, 15, 12];
const CASING_SELECTED: ExpressionSpecification = ["interpolate", ["linear"], ["zoom"], 12, 9, 15, 15];

/** The alternatives on one map: the selected one in signal orange, the others muted. */
export default function RoutesMap({
  routes,
  selectedId,
  onSelect,
  fromLabel,
  toLabel,
  streets,
  hour,
}: {
  routes: PlannedRoute[];
  selectedId: string;
  onSelect: (id: string) => void;
  fromLabel: string;
  toLabel: string;
  /** Scored streets drawn faintly underneath, so you can see why a route is calmer. */
  streets?: StreetSegment[];
  hour: number;
}) {
  const theme = useResolvedTheme();
  const reduceMotion = usePrefersReducedMotion();
  const mapRef = useRef<MapRef>(null);
  const colors = BASE_COLORS[theme];
  const muted = theme === "dark" ? "#7f8ba1" : "#8794ab";

  const streetData = useMemo(() => (streets?.length ? streetsToGeoJSON(streets) : null), [streets]);
  const padding = typeof window !== "undefined" && window.innerWidth < 640 ? 36 : 80;

  const bounds = useMemo((): [[number, number], [number, number]] => {
    const [w, s, e, n] = bbox(routes.flatMap((r) => r.coordinates));
    return [
      [w, s],
      [e, n],
    ];
  }, [routes]);

  const key = routes.map((r) => r.coordinates[0].join(",")).join("|");
  const firstKey = useRef(key);
  useEffect(() => {
    // Re-frame when the trip changes (e.g. swapped), not on first render.
    if (key === firstKey.current) return;
    firstKey.current = key;
    mapRef.current?.fitBounds(bounds, { padding, duration: reduceMotion ? 0 : 700 });
  }, [key, bounds, reduceMotion, padding]);

  // The selected route is drawn last (on top). Layers are keyed by selection so
  // MapLibre re-adds them in that order instead of keeping the first insertion order.
  const ordered = [...routes].sort((a, b) => Number(a.id === selectedId) - Number(b.id === selectedId));
  const features = useMemo(
    () => new Map(routes.map((r) => [r.id, { type: "Feature" as const, properties: {}, geometry: { type: "LineString" as const, coordinates: r.coordinates } }])),
    [routes],
  );
  const layerId = (id: string) => `route-${id}-${id === selectedId ? 1 : 0}`;
  const labels = useMemo(() => placeLabels(routes, selectedId), [routes, selectedId]);
  const start = routes[0]?.coordinates[0];
  const end = routes[0]?.coordinates[routes[0].coordinates.length - 1];

  return (
    <BaseMap
      ref={mapRef}
      label={`Map of ${routes.length} route alternatives from ${fromLabel} to ${toLabel}. The selected route is highlighted.`}
      initialViewState={{ bounds, fitBoundsOptions: { padding } }}
      className="size-full"
      interactiveLayerIds={routes.map((r) => layerId(r.id))}
      onClick={(e) => {
        const id = e.features?.[0]?.layer.id.replace(/^route-/, "").replace(/-[01]$/, "");
        if (id) onSelect(id);
      }}
      cursor="pointer"
    >
      {streetData ? (
        <Source id="routes-streets" type="geojson" data={streetData}>
          <Layer
            id="routes-streets"
            type="line"
            layout={{ "line-cap": "round", "line-join": "round" }}
            paint={{
              "line-color": scoreColorExpression(["get", hourProp("overall", hour)], theme) as unknown as ExpressionSpecification,
              "line-width": ["interpolate", ["linear"], ["zoom"], 12, 1.2, 15, 3],
              "line-opacity": theme === "dark" ? 0.3 : 0.4,
            }}
          />
        </Source>
      ) : null}
      {ordered.map((r) => {
        const sel = r.id === selectedId;
        return (
          <Source key={`${r.id}-${sel}`} id={`src-${r.id}-${sel ? 1 : 0}`} type="geojson" data={features.get(r.id)!}>
            <Layer
              id={`casing-${r.id}-${sel ? 1 : 0}`}
              type="line"
              layout={{ "line-cap": "round", "line-join": "round" }}
              paint={{ "line-color": colors.casing, "line-width": sel ? CASING_SELECTED : CASING, "line-opacity": sel ? 0.95 : 0.7 }}
            />
            <Layer
              id={layerId(r.id)}
              type="line"
              layout={{ "line-cap": "round", "line-join": "round" }}
              paint={{ "line-color": sel ? "#ff5b1f" : muted, "line-width": sel ? WIDTH_SELECTED : WIDTH, "line-opacity": sel ? 1 : 0.75 }}
            />
          </Source>
        );
      })}

      {routes.map((r) => {
        const [lng, lat] = labels.get(r.id) ?? pointAlong(r.coordinates, 0.6);
        const sel = r.id === selectedId;
        return (
          <Marker key={`label-${r.id}`} longitude={lng} latitude={lat} anchor="bottom" offset={[0, -6]} style={{ zIndex: sel ? 3 : 2 }}>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onSelect(r.id);
              }}
              aria-pressed={sel}
              className={cn(
                "rounded-full border px-2.5 py-1 text-xs font-semibold whitespace-nowrap shadow-[var(--shadow-lift)] transition-transform hover:scale-105",
                sel ? "border-signal bg-signal text-asphalt-900" : "border-line-strong bg-surface text-fg",
              )}
            >
              {r.label} · <span className="font-num">{r.durationMin} min</span>
            </button>
          </Marker>
        );
      })}

      {start ? (
        <Marker longitude={start[0]} latitude={start[1]} anchor="center">
          <span className="block size-4 rounded-full border-[3px] border-white bg-asphalt-900 shadow" role="img" aria-label={`Start: ${fromLabel}`} />
        </Marker>
      ) : null}
      {end ? (
        <Marker longitude={end[0]} latitude={end[1]} anchor="center">
          <span className="relative flex size-5 items-center justify-center" role="img" aria-label={`Destination: ${toLabel}`}>
            <span className="absolute inset-0 animate-pulse-dot rounded-full bg-signal/40" />
            <span className="relative size-3.5 rounded-full border-[3px] border-white bg-signal shadow" />
          </span>
        </Marker>
      ) : null}
    </BaseMap>
  );
}
