import type { Feature, FeatureCollection, LineString } from "geojson";
import { overallScore } from "./score";
import type { MapMetric, StreetSegment } from "./types";

export type StreetFeatureProps = Record<string, number | string | boolean> & { id: string; name: string };

const PREFIX: Record<MapMetric, string> = { comfort: "c", safety: "s", air: "a", noise: "n", overall: "o" };

/** Property holding a metric's score for a given hour, e.g. `a8` = air at 08:00. */
export function hourProp(metric: MapMetric, hour: number) {
  return `${PREFIX[metric]}${hour}`;
}

/**
 * Flattens hourly scores into primitive properties (c0…c23, s0…, a0…, n0…, o0…)
 * so MapLibre can colour streets with a plain ["get", "a8"] expression.
 */
export function streetsToGeoJSON(streets: StreetSegment[]): FeatureCollection<LineString, StreetFeatureProps> {
  return {
    type: "FeatureCollection",
    features: streets.map((s): Feature<LineString, StreetFeatureProps> => {
      const props: StreetFeatureProps = { id: s.id, name: s.name, bikeLane: s.bikeLane };
      for (let h = 0; h < 24; h++) {
        const c = s.hourly.comfort[h];
        const sa = s.hourly.safety[h];
        const a = s.hourly.air[h];
        const n = s.hourly.noise[h];
        props[`c${h}`] = c;
        props[`s${h}`] = sa;
        props[`a${h}`] = a;
        props[`n${h}`] = n;
        props[`o${h}`] = overallScore({ comfort: c, safety: sa, air: a, noise: n });
      }
      return { type: "Feature", id: s.id, properties: props, geometry: { type: "LineString", coordinates: s.coordinates } };
    }),
  };
}

export function scoreAt(s: StreetSegment, metric: MapMetric, hour: number) {
  if (metric === "overall") {
    return overallScore({ comfort: s.hourly.comfort[hour], safety: s.hourly.safety[hour], air: s.hourly.air[hour], noise: s.hourly.noise[hour] });
  }
  return s.hourly[metric][hour];
}

/** The 24 hourly scores of a street for one metric. */
export function hourlyValues(s: StreetSegment, metric: MapMetric) {
  return Array.from({ length: 24 }, (_, h) => scoreAt(s, metric, h));
}

/**
 * Best (or worst) window of `len` hours within riding hours (07:00–21:00),
 * e.g. the calmest two hours of the day to ride a street.
 */
export function scoreWindow(values: number[], pick: "best" | "worst", len = 2, from = 7, to = 20) {
  let start = from;
  let avg = pick === "best" ? -Infinity : Infinity;
  for (let h = from; h + len - 1 <= to; h++) {
    let sum = 0;
    for (let k = 0; k < len; k++) sum += values[h + k];
    const a = sum / len;
    if (pick === "best" ? a > avg : a < avg) {
      avg = a;
      start = h;
    }
  }
  return { start, end: start + len, avg: Math.round(avg) };
}

/** Accent- and case-insensitive text for searching street names. */
export function searchable(text: string) {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}
