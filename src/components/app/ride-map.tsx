"use client";

import type { Feature, LineString } from "geojson";
import type { ExpressionSpecification } from "maplibre-gl";
import { useMemo } from "react";
import { Layer, Marker, Popup, Source } from "react-map-gl/maplibre";
import { BaseMap } from "@/components/map/base-map";
import { BASE_COLORS } from "@/components/map/map-style";
import { boundsOf } from "@/lib/geo";
import { useResolvedTheme } from "@/lib/hooks/use-resolved-theme";
import { airScoreFromPm, comfortScoreFromVib, noiseScoreFromDb, scoreColorExpression } from "@/lib/score";
import type { ActivityDetail, RideEvent } from "@/lib/types";
import { EVENT_META } from "./ride-events";

/** Local score of a sample: what the street felt like at that exact point. */
export function localScore(vib: number, pm: number, db: number) {
  return Math.round(comfortScoreFromVib(vib) * 0.4 + airScoreFromPm(pm) * 0.3 + noiseScoreFromDb(db) * 0.3);
}

export default function RideMap({
  activity,
  activeIndex,
  selectedEvent,
  onSelectEvent,
}: {
  activity: ActivityDetail;
  activeIndex: number | null;
  selectedEvent: number | null;
  onSelectEvent: (i: number | null) => void;
}) {
  const theme = useResolvedTheme();
  const { route, samples } = activity;

  const segments = useMemo(() => {
    const features: Feature<LineString, { score: number }>[] = [];
    const chunk = 3;
    for (let i = 0; i < samples.length - 1; i += chunk) {
      const group = samples.slice(i, Math.min(samples.length, i + chunk + 1));
      const a = group[0][6];
      const b = group[group.length - 1][6];
      if (b <= a) continue;
      const score = Math.round(group.reduce((s, x) => s + localScore(x[3], x[4], x[5]), 0) / group.length);
      features.push({ type: "Feature", properties: { score }, geometry: { type: "LineString", coordinates: route.slice(a, b + 1) } });
    }
    return { type: "FeatureCollection" as const, features };
  }, [route, samples]);

  const bounds = useMemo(() => boundsOf(route), [route]);
  const cursor = activeIndex !== null ? route[samples[Math.min(activeIndex, samples.length - 1)][6]] : null;
  const colors = BASE_COLORS[theme];
  const ev = selectedEvent !== null ? activity.events[selectedEvent] : null;

  return (
    <BaseMap
      label={`Map of ${activity.title}, coloured by street score, with ${activity.events.length} events`}
      initialViewState={{ bounds, fitBoundsOptions: { padding: { top: 56, bottom: 56, left: 48, right: 48 } } }}
      className="size-full"
    >
      <Source id="ride-segments" type="geojson" data={segments}>
        <Layer id="ride-casing" type="line" layout={{ "line-cap": "round", "line-join": "round" }} paint={{ "line-color": colors.casing, "line-width": 10, "line-opacity": 0.9 }} />
        <Layer
          id="ride-line"
          type="line"
          layout={{ "line-cap": "round", "line-join": "round" }}
          paint={{ "line-color": scoreColorExpression(["get", "score"], theme) as unknown as ExpressionSpecification, "line-width": 5.5 }}
        />
      </Source>
      <Marker longitude={route[0][0]} latitude={route[0][1]} anchor="center">
        <span className="block size-4 rounded-full border-[3px] border-white bg-asphalt-900 shadow" aria-label="Start" role="img" />
      </Marker>
      <Marker longitude={route[route.length - 1][0]} latitude={route[route.length - 1][1]} anchor="center">
        <span className="block size-4 rounded-full border-[3px] border-asphalt-900 bg-white shadow" aria-label="Finish" role="img" />
      </Marker>
      {activity.events.map((e: RideEvent, i) => {
        const meta = EVENT_META[e.type];
        return (
          <Marker key={`${e.type}-${i}`} longitude={e.coordinates[0]} latitude={e.coordinates[1]} anchor="center">
            <button
              type="button"
              onClick={(evt) => {
                evt.stopPropagation();
                onSelectEvent(selectedEvent === i ? null : i);
              }}
              aria-label={`${meta.label} at ${e.time}, ${e.value} ${meta.unit}`}
              aria-pressed={selectedEvent === i}
              className="flex size-8 items-center justify-center rounded-full border-2 border-white shadow-lg transition-transform hover:scale-110"
              style={{ background: meta.color }}
            >
              <meta.icon className="size-4 text-asphalt-900" strokeWidth={2.4} />
            </button>
          </Marker>
        );
      })}
      {ev ? (
        <Popup longitude={ev.coordinates[0]} latitude={ev.coordinates[1]} anchor="bottom" offset={22} closeButton={false} onClose={() => onSelectEvent(null)}>
          <p className="text-[13px] font-semibold">
            {EVENT_META[ev.type].label} · <span className="font-mono text-xs text-fg-muted">{ev.time}</span>
          </p>
          <p className="mt-0.5 text-xs text-fg-muted">
            <span className="font-num font-semibold text-fg">{ev.value}</span> {EVENT_META[ev.type].unit}
            {ev.street ? ` · ${ev.street}` : ""}
          </p>
        </Popup>
      ) : null}
      {cursor ? (
        <Marker longitude={cursor[0]} latitude={cursor[1]} anchor="center">
          <span className="relative block size-5" aria-hidden>
            <span className="absolute inset-0 rounded-full bg-signal/30" />
            <span className="absolute inset-[5px] rounded-full border-2 border-white bg-signal" />
          </span>
        </Marker>
      ) : null}
    </BaseMap>
  );
}
