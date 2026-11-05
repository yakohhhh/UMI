"use client";

import type { Feature, LineString } from "geojson";
import { Flag } from "lucide-react";
import type { ExpressionSpecification } from "maplibre-gl";
import { useMemo } from "react";
import { Layer, Marker, Popup, Source } from "react-map-gl/maplibre";
import { BaseMap } from "@/components/map/base-map";
import { BASE_COLORS } from "@/components/map/map-style";
import { CURRENT_ATHLETE_ID } from "@/lib/api";
import { boundsOf } from "@/lib/geo";
import { useResolvedTheme } from "@/lib/hooks/use-resolved-theme";
import { airScoreFromPm, comfortScoreFromVib, noiseScoreFromDb, scoreColorExpression } from "@/lib/score";
import type { ActivityDetail, RideEvent, RideFlag } from "@/lib/types";
import { cn } from "@/lib/utils";
import { CAUSE_META, EVENT_META, flagReach, FLAG_SOURCE_LABEL, FLAG_STATUS_META, HAZARD_META } from "./ride-events";

/** Local score of a sample: what the street felt like at that exact point. */
export function localScore(vib: number, pm: number, db: number) {
  return Math.round(comfortScoreFromVib(vib) * 0.4 + airScoreFromPm(pm) * 0.3 + noiseScoreFromDb(db) * 0.3);
}

const plural = (n: number, one: string, many: string) => `${n} ${n === 1 ? one : many}`;

export default function RideMap({
  activity,
  activeIndex,
  selectedId,
  onSelect,
}: {
  activity: ActivityDetail;
  activeIndex: number | null;
  /** Id of the selected event or flag. */
  selectedId: string | null;
  onSelect: (id: string | null) => void;
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
  const own = activity.athleteId === CURRENT_ATHLETE_ID;
  const ev = activity.events.find((e) => e.id === selectedId) ?? null;
  const fl = ev ? null : (activity.flags.find((f) => f.id === selectedId) ?? null);
  const Cause = ev?.cause ? CAUSE_META[ev.cause].icon : null;
  const toggle = (id: string) => onSelect(selectedId === id ? null : id);
  const counts = [activity.events.length ? plural(activity.events.length, "event", "events") : "", activity.flags.length ? plural(activity.flags.length, "flag", "flags") : ""].filter(Boolean);

  return (
    <BaseMap
      label={`Map of ${activity.title}, coloured by street score, with ${counts.length ? counts.join(" and ") : "no moments"}`}
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
      {activity.events.map((e: RideEvent) => {
        const meta = EVENT_META[e.type];
        const selected = selectedId === e.id;
        return (
          <Marker key={e.id} longitude={e.coordinates[0]} latitude={e.coordinates[1]} anchor="center">
            <button
              type="button"
              onClick={(evt) => {
                evt.stopPropagation();
                toggle(e.id);
              }}
              aria-label={`${meta.label} at ${e.time}, ${e.value} ${meta.unit}${e.cause ? `, ${CAUSE_META[e.cause].label.toLowerCase()}` : ""}`}
              aria-pressed={selected}
              className={cn("flex size-8 items-center justify-center rounded-full border-2 border-white shadow-lg transition-transform hover:scale-110", selected && "scale-110")}
              style={{ background: meta.color }}
            >
              <meta.icon className="size-4 text-asphalt-900" strokeWidth={2.4} />
            </button>
          </Marker>
        );
      })}
      {/* Flags are the rider's own action: a rounded square with a signal border, so they never read as measured events. */}
      {activity.flags.map((f) => {
        const hazard = f.kind ? HAZARD_META[f.kind] : null;
        const Icon = hazard?.icon ?? Flag;
        const selected = selectedId === f.id;
        return (
          <Marker key={f.id} longitude={f.coordinates[0]} latitude={f.coordinates[1]} anchor="center">
            <button
              type="button"
              onClick={(evt) => {
                evt.stopPropagation();
                toggle(f.id);
              }}
              aria-label={`${hazard ? `${hazard.label} flag` : "Flag, no word said"} at ${f.time}, ${FLAG_STATUS_META[f.status].label}`}
              aria-pressed={selected}
              className={cn(
                "flex size-8 items-center justify-center rounded-[10px] border-[2.5px] border-signal shadow-lg ring-2 ring-white transition-transform hover:scale-110",
                selected && "scale-110",
              )}
              style={{ background: hazard?.color ?? "#ffffff" }}
            >
              <Icon className={cn("size-4", hazard ? "text-asphalt-900" : "text-signal-ink")} strokeWidth={2.4} />
            </button>
          </Marker>
        );
      })}
      {ev ? (
        <Popup key={ev.id} longitude={ev.coordinates[0]} latitude={ev.coordinates[1]} anchor="bottom" offset={22} closeButton={false} onClose={() => onSelect(null)}>
          <p className="text-[13px] font-semibold">
            {EVENT_META[ev.type].label} · <span className="font-mono text-xs text-fg-muted">{ev.time}</span>
          </p>
          <p className="mt-0.5 text-xs text-fg-muted">
            <span className="font-num font-semibold text-fg">{ev.value}</span> {EVENT_META[ev.type].unit}
            {ev.street ? ` · ${ev.street}` : ""}
          </p>
          {ev.type === "hard_brake" && ev.cause && Cause ? (
            <p className="mt-1.5 flex items-center gap-1.5 text-xs text-fg">
              <Cause className="size-3.5 shrink-0" aria-hidden />
              {CAUSE_META[ev.cause].label}
            </p>
          ) : ev.type === "hard_brake" && own ? (
            <p className="mt-1.5 text-xs text-fg-muted">Why did you brake? Answer under Moments.</p>
          ) : null}
        </Popup>
      ) : null}
      {fl ? <FlagPopup key={fl.id} f={fl} own={own} onClose={() => onSelect(null)} /> : null}
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

function FlagPopup({ f, own, onClose }: { f: RideFlag; own: boolean; onClose: () => void }) {
  const status = FLAG_STATUS_META[f.status];
  return (
    <Popup longitude={f.coordinates[0]} latitude={f.coordinates[1]} anchor="bottom" offset={22} closeButton={false} onClose={onClose} maxWidth="260px">
      <p className="text-[13px] font-semibold">
        {f.kind ? HAZARD_META[f.kind].label : "Flag · no word said"} · <span className="font-mono text-xs text-fg-muted">{f.time}</span>
      </p>
      <p className="mt-0.5 text-xs text-fg-muted">
        {FLAG_SOURCE_LABEL[f.source].label}
        {f.street ? ` · ${f.street}` : ""}
      </p>
      <p className="mt-1.5 flex items-center gap-1.5 text-xs text-fg">
        <status.icon className="size-3.5 shrink-0" aria-hidden />
        <span className="font-medium">{status.label}</span>
        <span className="text-fg-muted">· {flagReach(f, own)}</span>
      </p>
      {f.proof ? <p className="mt-1 text-xs text-fg-muted">{f.proof}</p> : null}
      {!f.kind && own ? <p className="mt-1 text-xs text-fg-muted">What was it? One tap under Moments.</p> : null}
    </Popup>
  );
}
