/**
 * Mock data loaders. JSON files are imported lazily so each page only ships
 * the datasets it needs. Dates are shifted by whole weeks so the demo always
 * looks recent while keeping weekday patterns intact.
 */
import type {
  ActivityDetail,
  ActivitySample,
  ActivitySegment,
  ActivitySummary,
  AirNoiseCell,
  Athlete,
  BrakeHotspot,
  DistrictStat,
  ExposureDay,
  GeoFeatureCollection,
  Kpi,
  LngLat,
  MonthlyBrakes,
  PlannedRoute,
  Pothole,
  StreetSegment,
  SurfaceRankRow,
} from "../types";
import type { MultiPolygon, Polygon } from "geojson";

/** The moment the mock data was generated (Thursday 15 Oct 2026, 19:10 Barcelona). */
export const MOCK_ANCHOR = new Date("2026-10-15T19:10:00+02:00");

const WEEK_MS = 7 * 86_400_000;
/** Whole weeks between the anchor and now (never negative). */
export function weekShiftMs(now = Date.now()) {
  const weeks = Math.floor((now - MOCK_ANCHOR.getTime()) / WEEK_MS);
  return Math.max(0, weeks) * WEEK_MS;
}
export function mockNow() {
  return new Date(MOCK_ANCHOR.getTime() + weekShiftMs());
}
const shiftIso = (iso: string) => new Date(new Date(iso).getTime() + weekShiftMs()).toISOString();
const shiftDay = (day: string) => shiftIso(`${day}T12:00:00Z`).slice(0, 10);

let cache: Record<string, unknown> = {};
async function once<T>(key: string, load: () => Promise<T>): Promise<T> {
  if (!(key in cache)) cache[key] = await load();
  return cache[key] as T;
}
export function clearMockCache() {
  cache = {};
}

export const loadStreets = () =>
  once("streets", async () => (await import("./data/streets.json")).default as unknown as StreetSegment[]);

export const loadDistrictsGeo = () =>
  once(
    "districtsGeo",
    async () => (await import("./data/districts.json")).default as unknown as GeoFeatureCollection<Polygon | MultiPolygon, { name: string; code: string }>,
  );

export const loadCityOutline = () =>
  once("cityOutline", async () => (await import("./data/city-outline.json")).default as unknown as GeoFeatureCollection<Polygon | MultiPolygon>);

export const loadPotholes = () =>
  once("potholes", async () => ((await import("./data/potholes.json")).default as unknown as Pothole[]).map((p) => ({ ...p, firstSeen: shiftDay(p.firstSeen) })));

export const loadHotspots = () => once("hotspots", async () => (await import("./data/hotspots.json")).default as unknown as BrakeHotspot[]);

export const loadRoutes = () => once("routes", async () => (await import("./data/routes.json")).default as unknown as PlannedRoute[]);

export const loadPeople = () =>
  once("people", async () => (await import("./data/people.json")).default as unknown as { people: Record<string, Athlete>; friends: string[] });

export const loadActivities = () =>
  once("activities", async () => {
    const raw = (await import("./data/activities.json")).default as unknown as ActivitySummary[];
    return raw.map((a) => ({ ...a, startedAt: shiftIso(a.startedAt) }));
  });

export const loadActivityDetails = () =>
  once(
    "activityDetails",
    async () =>
      (await import("./data/activity-details.json")).default as unknown as Record<
        string,
        { route: LngLat[]; samples: ActivitySample[]; segments: ActivitySegment[] }
      >,
  );

export async function loadActivityDetail(id: string): Promise<ActivityDetail | null> {
  const [list, details] = await Promise.all([loadActivities(), loadActivityDetails()]);
  const summary = list.find((a) => a.id === id);
  const detail = details[id];
  if (!summary || !detail) return null;
  return { ...summary, ...detail };
}

export const loadExposure = () =>
  once("exposure", async () => {
    const raw = (await import("./data/exposure.json")).default as unknown as ExposureDay[];
    return raw.map((d) => ({ ...d, date: shiftDay(d.date) }));
  });

interface CityJson {
  generatedAt: string;
  kpis: Kpi[];
  districts: DistrictStat[];
  monthlyHardBrakes: MonthlyBrakes[];
  airNoise: AirNoiseCell[][];
}
export const loadCity = () => once("city", async () => (await import("./data/city.json")).default as unknown as CityJson);

export const loadSurfaceRanking = () =>
  once("surfaceRanking", async () => (await import("./data/surface-ranking.json")).default as unknown as SurfaceRankRow[]);
