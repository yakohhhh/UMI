"use client";

import type { ExpressionSpecification } from "maplibre-gl";
import { useMemo, useState } from "react";
import { Layer, Marker, Source, type MapLayerMouseEvent } from "react-map-gl/maplibre";
import { BaseMap } from "@/components/map/base-map";
import { useResolvedTheme } from "@/lib/hooks/use-resolved-theme";
import { BAND_COLORS } from "@/lib/score";
import type { DistrictStat, GeoFeatureCollection } from "@/lib/types";
import { cn } from "@/lib/utils";
import type { MultiPolygon, Polygon } from "geojson";
import { DISTRICT_METRICS, type DistrictMetric } from "./district-metrics";

function ringArea(ring: number[][]) {
  let a = 0;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) a += ring[j][0] * ring[i][1] - ring[i][0] * ring[j][1];
  return a / 2;
}

function ringCentroid(ring: number[][]): [number, number] {
  let x = 0;
  let y = 0;
  let a = 0;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const f = ring[j][0] * ring[i][1] - ring[i][0] * ring[j][1];
    x += (ring[j][0] + ring[i][0]) * f;
    y += (ring[j][1] + ring[i][1]) * f;
    a += f;
  }
  return a ? [x / (3 * a), y / (3 * a)] : [ring[0][0], ring[0][1]];
}

/** Hand-placed anchors where the centroid falls on a mountain or the port. */
const LABEL_NUDGE: Record<string, [number, number]> = {
  "Sants-Montjuïc": [2.1395, 41.3735],
};

/**
 * District choropleth. Hover for the figures, click to add / remove a district
 * from the filters (all City Insights pages follow).
 */
export default function DistrictMap({
  geo,
  stats,
  metric,
  selected,
  onToggle,
}: {
  geo: GeoFeatureCollection<Polygon | MultiPolygon, { name: string; code: string }>;
  stats: DistrictStat[];
  metric: DistrictMetric;
  selected: string[];
  onToggle: (name: string) => void;
}) {
  const theme = useResolvedTheme();
  const [hover, setHover] = useState<{ name: string; x: number; y: number } | null>(null);
  const meta = DISTRICT_METRICS[metric];
  const byName = useMemo(() => new Map(stats.map((d) => [d.name, d])), [stats]);

  const data = useMemo(
    () => ({
      ...geo,
      features: geo.features.map((f) => {
        const d = byName.get(f.properties.name);
        return {
          ...f,
          properties: {
            ...f.properties,
            band: d ? meta.band(d) : "none",
            selected: selected.includes(f.properties.name),
            dimmed: selected.length > 0 && !selected.includes(f.properties.name),
          },
        };
      }),
    }),
    [geo, byName, meta, selected],
  );

  // Label anchors: area-weighted centroid of each district's largest ring.
  const labels = useMemo(
    () =>
      geo.features.map((f) => {
        const polys = f.geometry.type === "Polygon" ? [f.geometry.coordinates] : f.geometry.coordinates;
        let best = polys[0][0];
        let bestArea = 0;
        for (const p of polys) {
          const a = Math.abs(ringArea(p[0]));
          if (a > bestArea) {
            bestArea = a;
            best = p[0];
          }
        }
        const d = byName.get(f.properties.name);
        return { name: f.properties.name, at: LABEL_NUDGE[f.properties.name] ?? ringCentroid(best), value: d ? meta.format(d) : "" };
      }),
    [geo, byName, meta],
  );

  const c = BAND_COLORS[theme];
  const fill: ExpressionSpecification = ["match", ["get", "band"], "good", c.good, "mid", c.mid, "bad", c.bad, theme === "dark" ? "#26344f" : "#d9d4c9"];
  const hovered = hover ? byName.get(hover.name) : undefined;

  const onMove = (e: MapLayerMouseEvent) => {
    const f = e.features?.[0];
    setHover(f ? { name: String(f.properties?.name), x: e.point.x, y: e.point.y } : null);
  };

  return (
    <div className="relative size-full">
      <BaseMap
        label={`Barcelona districts coloured by ${meta.label.toLowerCase()}. Click a district to filter.`}
        initialViewState={{ longitude: 2.1565, latitude: 41.4005, zoom: 11.05 }}
        className="size-full"
        interactiveLayerIds={["districts-fill"]}
        cursor={hover ? "pointer" : "grab"}
        onMouseMove={onMove}
        onMouseLeave={() => setHover(null)}
        onClick={(e) => {
          const f = e.features?.[0];
          if (f) onToggle(String(f.properties?.name));
        }}
        scrollZoom={false}
      >
        <Source id="districts" type="geojson" data={data}>
          <Layer
            id="districts-fill"
            type="fill"
            paint={{
              "fill-color": fill,
              "fill-opacity": ["case", ["get", "dimmed"], 0.12, theme === "dark" ? 0.68 : 0.58],
            }}
          />
          <Layer
            id="districts-line"
            type="line"
            paint={{
              "line-color": theme === "dark" ? "#0b1220" : "#ffffff",
              "line-width": 1.5,
            }}
          />
          <Layer
            id="districts-selected"
            type="line"
            filter={["any", ["==", ["get", "selected"], true], ["==", ["get", "name"], hover?.name ?? ""]]}
            paint={{ "line-color": ["case", ["get", "selected"], "#ff5b1f", theme === "dark" ? "#f3f1ec" : "#0b1220"], "line-width": 2.5 }}
          />
        </Source>
        {labels.map((l) => (
          <Marker key={l.name} longitude={l.at[0]} latitude={l.at[1]} anchor="center" style={{ pointerEvents: "none" }}>
            <span
              className={cn(
                "pointer-events-none block text-center text-[10.5px] leading-tight font-semibold whitespace-nowrap [text-shadow:0_0_3px_var(--bg),0_0_6px_var(--bg)]",
                selected.length && !selected.includes(l.name) ? "text-fg-subtle" : "text-fg",
              )}
            >
              {l.name}
              <span className="block font-num text-[10px] font-medium text-fg-muted">{l.value}</span>
            </span>
          </Marker>
        ))}
      </BaseMap>
      {hover && hovered ? (
        <div
          className="pointer-events-none absolute top-0 left-0 z-10 hidden w-56 rounded-xl border border-line bg-surface/95 px-3 py-2.5 shadow-[var(--shadow-lift)] backdrop-blur md:block"
          style={{ transform: `translate(${hover.x}px, ${hover.y}px) translate(-50%, calc(-100% - 14px))` }}
          aria-hidden
        >
          <p className="text-[13px] font-semibold text-fg">{hovered.name}</p>
          <dl className="mt-1.5 grid grid-cols-2 gap-x-3 gap-y-1 text-[11px]">
            {Object.values(DISTRICT_METRICS).map((m) => (
              <div key={m.id} className="contents">
                <dt className={m.id === metric ? "font-medium text-fg" : "text-fg-muted"}>{m.short}</dt>
                <dd className="text-right font-num text-fg">{m.format(hovered)}</dd>
              </div>
            ))}
          </dl>
          <p className="mt-2 text-[10px] text-fg-subtle">{selected.includes(hovered.name) ? "Click to remove from the filter" : "Click to filter by this district"}</p>
        </div>
      ) : null}
    </div>
  );
}
