"use client";

import type { ExpressionSpecification } from "maplibre-gl";
import { useEffect, useMemo, useRef, useState } from "react";
import { Layer, Source, type MapLayerMouseEvent, type MapRef } from "react-map-gl/maplibre";
import { CAUSE_META } from "@/components/app/ride-events";
import { BaseMap } from "@/components/map/base-map";
import { hourLabel } from "@/lib/format";
import { usePrefersReducedMotion } from "@/lib/hooks/use-media-query";
import { useResolvedTheme } from "@/lib/hooks/use-resolved-theme";
import type { BrakeCause, BrakeHotspot } from "@/lib/types";
import { hotspotRadius } from "./hotspot-scale";

export default function HotspotMap({
  hotspots,
  activeId,
  onActive,
  causeStyle,
}: {
  hotspots: BrakeHotspot[];
  activeId: string | null;
  onActive: (id: string | null) => void;
  /** City-facing cause names and bar colours, so the popup matches the table; falls back to the rider app's labels. */
  causeStyle?: Partial<Record<BrakeCause, { label: string; color: string }>>;
}) {
  const theme = useResolvedTheme();
  const reduceMotion = usePrefersReducedMotion();
  const mapRef = useRef<MapRef>(null);
  const [hover, setHover] = useState<{ id: string; x: number; y: number } | null>(null);
  const max = Math.max(1, ...hotspots.map((h) => h.hardBrakes30d));

  const data = useMemo(
    () => ({
      type: "FeatureCollection" as const,
      features: [...hotspots]
        .sort((a, b) => b.hardBrakes30d - a.hardBrakes30d) // big circles first, small ones on top
        .map((h) => ({ type: "Feature" as const, properties: { id: h.id, r: hotspotRadius(h.hardBrakes30d, max), rising: h.trend > 0 }, geometry: { type: "Point" as const, coordinates: h.coordinates } })),
    }),
    [hotspots, max],
  );

  useEffect(() => {
    if (!activeId || hover?.id === activeId) return;
    const h = hotspots.find((x) => x.id === activeId);
    const map = mapRef.current;
    if (!h || !map) return;
    if (map.getBounds().contains(h.coordinates)) return;
    map.easeTo({ center: h.coordinates, duration: reduceMotion ? 0 : 600 });
  }, [activeId, hotspots, hover?.id, reduceMotion]);

  const onMove = (e: MapLayerMouseEvent) => {
    const f = e.features?.[0];
    if (!f) {
      setHover(null);
      onActive(null);
      return;
    }
    const id = String(f.properties?.id);
    setHover({ id, x: e.point.x, y: e.point.y });
    onActive(id);
  };

  const h = hover ? hotspots.find((x) => x.id === hover.id) : undefined;
  // top named causes only: "other" is a bundle of small ones and says nothing on its own
  const why = (h?.causes ?? [])
    .filter((c): c is { cause: BrakeCause; share: number } => c.cause !== "other")
    .sort((a, b) => b.share - a.share)
    .slice(0, 3);
  const radius: ExpressionSpecification = ["get", "r"];

  return (
    <div className="relative size-full">
      <BaseMap
        ref={mapRef}
        label={`Map of ${hotspots.length} hard-brake hotspots, circle size proportional to the number of hard brakes.`}
        initialViewState={{ longitude: 2.168, latitude: 41.3935, zoom: 12.6 }}
        className="size-full"
        interactiveLayerIds={["hotspots"]}
        cursor={hover ? "pointer" : "grab"}
        onMouseMove={onMove}
        onMouseLeave={() => {
          setHover(null);
          onActive(null);
        }}
      >
        <Source id="hotspots" type="geojson" data={data}>
          <Layer
            id="hotspots"
            type="circle"
            paint={{
              "circle-radius": radius,
              "circle-color": "#ff5b1f",
              "circle-opacity": ["case", ["==", ["get", "id"], activeId ?? ""], 0.75, 0.3],
              "circle-stroke-color": ["case", ["==", ["get", "id"], activeId ?? ""], theme === "dark" ? "#ffffff" : "#0b1220", "#ff5b1f"],
              "circle-stroke-width": ["case", ["==", ["get", "id"], activeId ?? ""], 2, 1.2],
            }}
          />
          <Layer id="hotspots-core" type="circle" paint={{ "circle-radius": 2.2, "circle-color": theme === "dark" ? "#f3f1ec" : "#0b1220" }} />
        </Source>
      </BaseMap>
      {hover && h ? (
        <div
          className="pointer-events-none absolute top-0 left-0 z-10 hidden w-60 rounded-xl border border-line bg-surface/95 px-3 py-2.5 shadow-[var(--shadow-lift)] backdrop-blur md:block"
          style={{ transform: `translate(${hover.x}px, ${hover.y}px) translate(-50%, calc(-100% - 18px))` }}
          aria-hidden
        >
          <p className="text-[13px] leading-snug font-semibold text-fg">{h.label}</p>
          <p className="mt-1 text-xs text-fg-muted">
            <span className="font-num font-semibold text-fg">{h.hardBrakes30d}</span> hard brakes · peak {hourLabel(h.peakHour)}
          </p>
          <p className="text-xs text-fg-muted">
            avg <span className="font-num text-fg">{h.avgDecel.toFixed(1)}</span> m/s² ·{" "}
            <span className={h.trend > 0 ? "text-bad" : "text-good"}>
              {h.trend > 0 ? "+" : ""}
              {h.trend}% vs prev.
            </span>
          </p>
          {why.length ? (
            <div className="mt-2 border-t border-line pt-2">
              <p className="label-mono text-[10px] text-fg-subtle">
                Why riders brake{h.answeredBy ? ` · ${h.answeredBy} riders` : ""}
              </p>
              <ul className="mt-1 space-y-0.5 text-xs text-fg-muted">
                {why.map((c) => {
                  const m = CAUSE_META[c.cause];
                  const s = causeStyle?.[c.cause];
                  return (
                    <li key={c.cause} className="flex items-center gap-1.5">
                      {s ? <span className="size-2 shrink-0 rounded-[2px]" style={{ background: s.color }} aria-hidden /> : null}
                      <m.icon className="size-3.5 shrink-0 text-fg-subtle" aria-hidden />
                      <span className="min-w-0 flex-1 truncate">{s?.label ?? m.label}</span>
                      <span className="font-num font-semibold text-fg">{Math.round(c.share * 100)}%</span>
                    </li>
                  );
                })}
              </ul>
            </div>
          ) : (
            <p className="mt-1.5 text-[11px] text-fg-subtle">Why riders brake: not enough answers yet</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
