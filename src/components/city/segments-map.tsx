"use client";

import type { ExpressionSpecification } from "maplibre-gl";
import { useEffect, useMemo, useRef } from "react";
import { Layer, Source, type MapRef } from "react-map-gl/maplibre";
import { BaseMap } from "@/components/map/base-map";
import { BASE_COLORS } from "@/components/map/map-style";
import { boundsOf } from "@/lib/geo";
import { usePrefersReducedMotion } from "@/lib/hooks/use-media-query";
import { useResolvedTheme } from "@/lib/hooks/use-resolved-theme";
import { scoreColorExpression } from "@/lib/score";
import type { LngLat } from "@/lib/types";

export interface MapSegment {
  id: string;
  coordinates: LngLat[];
  value: number;
  label: string;
}

/**
 * Street segments coloured by a 0–100 index, linked to a table: `activeId`
 * highlights (and frames) a segment, `onHover` reports the one under the pointer.
 */
export default function SegmentsMap({
  segments,
  activeId,
  onHover,
  onPick,
  label,
}: {
  segments: MapSegment[];
  activeId: string | null;
  onHover: (id: string | null) => void;
  onPick?: (id: string) => void;
  label: string;
}) {
  const theme = useResolvedTheme();
  const reduceMotion = usePrefersReducedMotion();
  const mapRef = useRef<MapRef>(null);
  const colors = BASE_COLORS[theme];

  const data = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: segments.map((s) => ({ type: "Feature" as const, properties: { id: s.id, value: s.value, label: s.label }, geometry: { type: "LineString" as const, coordinates: s.coordinates } })),
    }),
    [segments],
  );

  // Frame the active segment if it is off screen.
  useEffect(() => {
    if (!activeId) return;
    const map = mapRef.current;
    const s = segments.find((x) => x.id === activeId);
    if (!map || !s) return;
    const b = map.getBounds();
    if (s.coordinates.every(([x, y]) => b.contains([x, y]))) return;
    map.fitBounds(boundsOf(s.coordinates), { padding: 90, maxZoom: 15, duration: reduceMotion ? 0 : 600 });
  }, [activeId, segments, reduceMotion]);

  return (
    <BaseMap
      ref={mapRef}
      label={label}
      initialViewState={{ longitude: 2.1705, latitude: 41.3935, zoom: 12.7 }}
      className="size-full"
      interactiveLayerIds={["segments"]}
      onMouseMove={(e) => onHover(e.features?.[0] ? String(e.features[0].properties?.id) : null)}
      onMouseLeave={() => onHover(null)}
      onClick={(e) => {
        const f = e.features?.[0];
        if (f && onPick) onPick(String(f.properties?.id));
      }}
      cursor={activeId ? "pointer" : "grab"}
    >
      <Source id="segments" type="geojson" data={data}>
        <Layer id="segments-casing" type="line" layout={{ "line-cap": "round", "line-join": "round" }} paint={{ "line-color": colors.casing, "line-width": ["interpolate", ["linear"], ["zoom"], 11, 3, 15, 10], "line-opacity": 0.8 }} />
        <Layer
          id="segments-halo"
          type="line"
          filter={["==", ["get", "id"], activeId ?? ""]}
          layout={{ "line-cap": "round", "line-join": "round" }}
          paint={{ "line-color": theme === "dark" ? "#ffffff" : "#0b1220", "line-width": ["interpolate", ["linear"], ["zoom"], 11, 7, 15, 16] }}
        />
        <Layer
          id="segments"
          type="line"
          layout={{ "line-cap": "round", "line-join": "round" }}
          paint={{
            "line-color": scoreColorExpression(["get", "value"], theme) as unknown as ExpressionSpecification,
            "line-width": ["interpolate", ["linear"], ["zoom"], 11, 1.8, 15, 6],
          }}
        />
      </Source>
    </BaseMap>
  );
}
