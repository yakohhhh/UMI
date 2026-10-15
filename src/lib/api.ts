/**
 * Data access layer. Every screen goes through these async functions.
 *
 * Today they resolve local mocks (src/lib/mock). Set NEXT_PUBLIC_API_URL to a
 * FastAPI deployment and the functions marked with an endpoint will call it
 * instead — response shapes are the types in ./types.
 */
import type {
  ActivityDetail,
  ActivitySummary,
  AirNoiseCell,
  Athlete,
  BestWindow,
  BrakeHotspot,
  CityAlert,
  CityFilters,
  CityOverview,
  ClipStatus,
  DistrictStat,
  ExposurePeriod,
  ExposureSummary,
  Kpi,
  MonthlyBrakes,
  PlannedRoute,
  Pothole,
  ProfileStats,
  StreetSegment,
  SurfaceRankRow,
  WeekStats,
} from "./types";
import {
  loadActivities,
  loadActivityDetail,
  loadCity,
  loadCityOutline,
  loadDistrictsGeo,
  loadExposure,
  loadHotspots,
  loadPeople,
  loadPotholes,
  loadRoutes,
  loadStreets,
  loadSurfaceRanking,
  mockNow,
  MOCK_ANCHOR,
} from "./mock";

const MOCK_ANCHOR_MS = MOCK_ANCHOR.getTime();
import { TIME_ZONE } from "./format";

const API_URL = process.env.NEXT_PUBLIC_API_URL;

export class ApiError extends Error {
  constructor(
    message: string,
    public status = 500,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/** Simulated network latency + optional failure (`?simulate=error|empty` in the URL). */
async function mock<T>(produce: () => Promise<T> | T, latency: [number, number] = [180, 420]): Promise<T> {
  const ms = latency[0] + Math.random() * (latency[1] - latency[0]);
  await new Promise((r) => setTimeout(r, ms));
  if (typeof window !== "undefined") {
    const sim = new URLSearchParams(window.location.search).get("simulate");
    if (sim === "error") throw new ApiError("The UMI API did not answer in time.", 503);
  }
  return produce();
}

export function isSimulatingEmpty() {
  return typeof window !== "undefined" && new URLSearchParams(window.location.search).get("simulate") === "empty";
}

async function endpoint<T>(path: string, fallback: () => Promise<T> | T, latency?: [number, number]): Promise<T> {
  if (!API_URL) return mock(fallback, latency);
  const res = await fetch(`${API_URL}${path}`, { headers: { accept: "application/json" } });
  if (!res.ok) throw new ApiError(`GET ${path} failed`, res.status);
  return (await res.json()) as T;
}

// ------------------------------------------------------------------ rider

export const CURRENT_ATHLETE_ID = "laia";

/** GET /v1/me */
export function getCurrentAthlete(): Promise<Athlete> {
  return endpoint("/v1/me", async () => (await loadPeople()).people[CURRENT_ATHLETE_ID], [60, 120]);
}

/** GET /v1/athletes/{id} */
export function getAthlete(id: string): Promise<Athlete | null> {
  return endpoint(`/v1/athletes/${id}`, async () => (await loadPeople()).people[id] ?? null, [40, 90]);
}

/** GET /v1/feed — the rider's own activities and the people they follow. */
export function getFeed(): Promise<ActivitySummary[]> {
  return endpoint("/v1/feed", async () => (isSimulatingEmpty() ? [] : loadActivities()));
}

/** GET /v1/activities/{id} */
export function getActivity(id: string): Promise<ActivityDetail | null> {
  return endpoint(`/v1/activities/${id}`, () => loadActivityDetail(id), [260, 520]);
}

export async function getFeaturedActivityId() {
  const list = await loadActivities();
  return (list.find((a) => a.featured) ?? list[0]).id;
}

/** GET /v1/me/week */
export function getWeekStats(): Promise<WeekStats> {
  return endpoint("/v1/me/week", async () => {
    const all = (await loadActivities()).filter((a) => a.athleteId === CURRENT_ATHLETE_ID);
    const now = mockNow();
    const dayKey = (d: Date) => new Intl.DateTimeFormat("en-CA", { timeZone: TIME_ZONE }).format(d); // YYYY-MM-DD
    const weekdayIdx = (d: Date) =>
      ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].indexOf(new Intl.DateTimeFormat("en-US", { timeZone: TIME_ZONE, weekday: "short" }).format(d));
    const todayIdx = weekdayIdx(now);
    const mondayKey = dayKey(new Date(now.getTime() - todayIdx * 86_400_000));
    const week = all.filter((a) => dayKey(new Date(a.startedAt)) >= mondayKey);
    const labels = ["M", "T", "W", "T", "F", "S", "S"];
    const days = labels.map((label, i) => ({
      label,
      isToday: i === todayIdx,
      km: Math.round(week.filter((a) => weekdayIdx(new Date(a.startedAt)) === i).reduce((s, a) => s + a.distanceM, 0) / 100) / 10,
    }));
    return {
      distanceKm: Math.round(week.reduce((s, a) => s + a.distanceM, 0) / 100) / 10,
      movingTimeS: week.reduce((s, a) => s + a.movingTimeS, 0),
      rides: week.filter((a) => a.type === "ride").length,
      runs: week.filter((a) => a.type === "run").length,
      goalKm: 40,
      streakDays: 9,
      days,
    };
  });
}

/** GET /v1/me/best-window — best time slot today for the rider's usual route. */
export function getBestWindow(): Promise<BestWindow> {
  return endpoint("/v1/me/best-window", () => ({
    title: "Today's best window",
    window: "18:00–19:30",
    detail: "Cleanest air on your way home: PM2.5 around 9 µg/m³ on Pg. de Sant Joan once the sea breeze sets in.",
    metric: "air" as const,
    score: 84,
  }));
}

/** GET /v1/me/clip */
export function getClipStatus(): Promise<ClipStatus> {
  return endpoint("/v1/me/clip", () => ({
    name: "UMI Clip",
    serial: "UMI-C1-0412-BCN",
    battery: 82,
    lastSync: new Date(mockNow().getTime() - 6 * 60_000).toISOString(),
    firmware: "1.4.2",
    connected: true,
    sensors: [
      { id: "gnss", label: "GNSS", enabled: true, detail: "Multi-band GPS + Galileo, 1 Hz" },
      { id: "imu", label: "IMU · 6-axis", enabled: true, detail: "Vibration & hard brakes, 100 Hz" },
      { id: "pm", label: "PM2.5", enabled: true, detail: "Laser particle sensor, every 10 s" },
      { id: "mic", label: "Microphone", enabled: true, detail: "dB(A) only — no audio is recorded" },
      { id: "env", label: "Temperature & humidity", enabled: true, detail: "Corrects the PM2.5 reading" },
    ],
  }));
}

// ------------------------------------------------------------------ map & routes

/** GET /v1/streets?bbox=… — scored street segments with hourly profiles. */
export function getStreetSegments(): Promise<StreetSegment[]> {
  return endpoint("/v1/streets", async () => (isSimulatingEmpty() ? [] : loadStreets()), [300, 600]);
}

/** GET /v1/potholes */
export function getPotholes(): Promise<Pothole[]> {
  return endpoint("/v1/potholes", () => loadPotholes());
}

/** GET /v1/hotspots/hard-brakes */
export function getBrakeHotspots(): Promise<BrakeHotspot[]> {
  return endpoint("/v1/hotspots/hard-brakes", () => loadHotspots());
}

/** GET /v1/districts — district boundaries (GeoJSON). */
export function getDistrictsGeo() {
  return endpoint("/v1/districts", () => loadDistrictsGeo(), [80, 160]);
}

/** GET /v1/city-outline */
export function getCityOutline() {
  return endpoint("/v1/city-outline", () => loadCityOutline(), [40, 80]);
}

export interface RouteRequest {
  from: string;
  to: string;
  /** "HH:MM", Europe/Madrid. Scores are forecast for that hour. */
  departAt?: string;
  /** Street segment the rider wants to pass through. */
  via?: string | null;
}

// Weekday traffic intensity by hour (0..1), same profile as the street scores.
const TRAFFIC = [0.16, 0.1, 0.07, 0.07, 0.11, 0.24, 0.52, 0.86, 1.0, 0.88, 0.74, 0.7, 0.73, 0.77, 0.72, 0.7, 0.76, 0.86, 0.95, 0.88, 0.68, 0.5, 0.36, 0.24];

/** The stored alternatives are computed for the 08:00 peak; lighter traffic means calmer, faster streets. */
function forecastRoute(r: PlannedRoute, hour: number): PlannedRoute {
  const calm = 1 - TRAFFIC[hour];
  const bump = (v: number, k: number) => Math.max(0, Math.min(100, Math.round(v + k * calm)));
  return {
    ...r,
    durationMin: Math.max(1, Math.round(r.durationMin * (0.85 + 0.15 * TRAFFIC[hour]))),
    scores: { comfort: bump(r.scores.comfort, 3), safety: bump(r.scores.safety, 14), air: bump(r.scores.air, 16), noise: bump(r.scores.noise, 22) },
  };
}

/** POST /v1/routes — Fastest / Calmest / Cleanest alternatives. */
export function planRoutes(req: RouteRequest): Promise<PlannedRoute[]> {
  return endpoint(
    "/v1/routes",
    async () => {
      if (isSimulatingEmpty()) return [];
      const hour = Number((req.departAt ?? "08:00").slice(0, 2));
      const routes = await loadRoutes();
      return routes.map((r) => forecastRoute(r, Number.isFinite(hour) ? Math.max(0, Math.min(23, hour)) : 8));
    },
    [450, 800],
  );
}

// ------------------------------------------------------------------ exposure & profile

const THRESHOLDS = { whoPm25Annual: 5, whoPm25Daily: 15, eu2030Pm25: 10, whoRoadNoise: 53 };

function aggregate(days: { date: string; pm25: number | null; db: number | null; rideMin: number }[], keyOf: (d: string) => string, labelOf: (k: string) => string) {
  const groups = new Map<string, typeof days>();
  for (const d of days) {
    const k = keyOf(d.date);
    if (!groups.has(k)) groups.set(k, []);
    groups.get(k)!.push(d);
  }
  return [...groups.entries()].map(([k, list]): ExposurePeriod => {
    const ridden = list.filter((d) => d.pm25 !== null);
    const minutes = ridden.reduce((s, d) => s + d.rideMin, 0);
    const wavg = (f: (d: (typeof list)[number]) => number) => (minutes ? ridden.reduce((s, d) => s + f(d) * d.rideMin, 0) / minutes : null);
    const pm = wavg((d) => d.pm25 ?? 0);
    const db = wavg((d) => d.db ?? 0);
    return { label: labelOf(k), start: k, pm25: pm === null ? null : Math.round(pm * 10) / 10, db: db === null ? null : Math.round(db * 10) / 10, rideMin: minutes };
  });
}

/** GET /v1/me/exposure?range=365d */
export function getExposure(): Promise<ExposureSummary> {
  return endpoint("/v1/me/exposure", async () => {
    const days = await loadExposure();
    const weekKey = (iso: string) => {
      const d = new Date(`${iso}T12:00:00Z`);
      d.setUTCDate(d.getUTCDate() - ((d.getUTCDay() + 6) % 7));
      return d.toISOString().slice(0, 10);
    };
    const weekly = aggregate(days, weekKey, (k) => new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "UTC" }).format(new Date(`${k}T12:00:00Z`))).slice(-16);
    const monthly = aggregate(days, (iso) => iso.slice(0, 7), (k) =>
      new Intl.DateTimeFormat("en-GB", { month: "short", timeZone: "UTC" }).format(new Date(`${k}-15T12:00:00Z`)),
    ).slice(-12);
    const ridden = days.filter((d) => d.pm25 !== null);
    const mins = ridden.reduce((s, d) => s + d.rideMin, 0);
    const avgPm = ridden.reduce((s, d) => s + (d.pm25 ?? 0) * d.rideMin, 0) / mins;
    const avgDb = ridden.reduce((s, d) => s + (d.db ?? 0) * d.rideMin, 0) / mins;
    const firstQ = monthly.slice(0, 3).filter((m) => m.pm25 !== null);
    const lastQ = monthly.slice(-3).filter((m) => m.pm25 !== null);
    const mean = (l: ExposurePeriod[]) => l.reduce((s, m) => s + (m.pm25 ?? 0), 0) / Math.max(1, l.length);
    const changePct = Math.round(((mean(lastQ) - mean(firstQ)) / mean(firstQ)) * 100);
    const lastWeeks = weekly.slice(-4);
    const prevWeeks = weekly.slice(-8, -4);
    const meanDb = (l: ExposurePeriod[]) => l.reduce((s, w) => s + (w.db ?? 0), 0) / Math.max(1, l.filter((w) => w.db !== null).length);
    return {
      days,
      weekly,
      monthly,
      thresholds: THRESHOLDS,
      totals: {
        avgPm25: Math.round(avgPm * 10) / 10,
        avgDb: Math.round(avgDb * 10) / 10,
        rideHours: Math.round(mins / 60),
        changePct,
        ridingDays: ridden.length,
        dbChange: Math.round((meanDb(lastWeeks) - meanDb(prevWeeks)) * 10) / 10,
      },
      contributors: [
        { street: "Avinguda Diagonal", share: 0.36, pm25: 15.8, minutesWeek: 52 },
        { street: "Passeig de Sant Joan", share: 0.22, pm25: 12.9, minutesWeek: 41 },
        { street: "Travessera de Gràcia", share: 0.17, pm25: 13.6, minutesWeek: 28 },
        { street: "Carrer de la Llacuna", share: 0.09, pm25: 10.4, minutesWeek: 19 },
      ],
      insights: [
        {
          id: "trend",
          tone: changePct < 0 ? "good" : "watch",
          title: `${Math.abs(changePct)}% ${changePct < 0 ? "less" : "more"} PM2.5 than last winter`,
          body: "Since you started taking Consell de Cent on the way home, your evening rides breathe noticeably cleaner air.",
        },
        {
          id: "morning",
          tone: "watch",
          title: "Mornings carry most of your dose",
          body: "Rides between 7:30 and 9:00 account for 61% of your weekly PM2.5 exposure. Leaving 20 minutes later lowers it by about a quarter.",
        },
        {
          id: "noise",
          tone: "neutral",
          title: `Average noise ${Math.round(avgDb)} dB(A) while riding`,
          body: `Above the WHO road-traffic guideline (${THRESHOLDS.whoRoadNoise} dB), mostly on Diagonal between Pg. de Sant Joan and Glòries.`,
        },
        {
          id: "limit",
          tone: lastWeeks.every((w) => (w.pm25 ?? 0) > THRESHOLDS.eu2030Pm25) ? "watch" : "good",
          title: "EU 2030 limit: 10 µg/m³",
          body: "Your ride-weighted average is above the 2030 limit, like most commuters on Barcelona's arterials. Calm streets bring it under.",
        },
      ],
    };
  });
}

/** GET /v1/me/profile */
export function getProfileStats(): Promise<ProfileStats> {
  return endpoint("/v1/me/profile", async () => {
    const acts = (await loadActivities()).filter((a) => a.athleteId === CURRENT_ATHLETE_ID);
    const best = acts.reduce((b, a) => (a.scores.comfort > b.scores.comfort ? a : b), acts[0]);
    return {
      totals: { distanceKm: 1846, rides: 412, runs: 6, hours: 131, streetsMapped: 186, since: "2025-11-03" },
      records: [
        { id: "longest", label: "Longest ride", value: "38.4 km", detail: "Seafront to Montgat and back", date: "2026-06-14" },
        { id: "comfort", label: "Smoothest commute", value: `Comfort ${best.scores.comfort}`, detail: best.title, date: best.startedAt.slice(0, 10) },
        { id: "calm", label: "Calmest week", value: "Overall 81", detail: "12 rides on green axes", date: "2026-09-21" },
        { id: "fast", label: "Fastest commute", value: "13m 08s", detail: "Gràcia → 22@, Sunday morning", date: "2026-05-10" },
      ],
      badges: [
        { id: "cartographer", label: "Street cartographer", description: "Measured 150 different street segments", earned: true },
        { id: "calm", label: "Calm commuter", description: "20 commutes with an overall score above 70", earned: true },
        { id: "pothole", label: "Pothole hunter", description: "Confirmed 10 potholes for the city", earned: true },
        { id: "early", label: "Early bird", description: "Rode before 7:30 on 15 days", earned: true },
        { id: "clean", label: "Clean air month", description: "A month under 10 µg/m³ average", earned: false, progress: 0.62 },
        { id: "century", label: "2,000 km", description: "Ride 2,000 km with UMI", earned: false, progress: 0.92 },
      ],
      contributions: {
        streetsImproved: 23,
        potholesConfirmed: 14,
        segmentsFirst: 9,
        topStreets: [
          { name: "Passeig de Sant Joan", passes: 168 },
          { name: "Avinguda Diagonal", passes: 151 },
          { name: "Carrer del Consell de Cent", passes: 77 },
          { name: "Carrer de la Llacuna", passes: 64 },
        ],
      },
      clubs: [
        { id: "gracia", name: "Gràcia Riders", challenge: "October distance", progress: 1240, goal: 2000, unit: "km", members: 86 },
        { id: "calm", name: "Calm Commute Challenge", challenge: "Rides scoring 70+ overall", progress: 12, goal: 20, unit: "rides", members: 412 },
        { id: "22", name: "22@ Bike to Work", challenge: "Office rides this week", progress: 318, goal: 400, unit: "rides", members: 204 },
      ],
    };
  });
}

// ------------------------------------------------------------------ City Insights

const PERIOD_FACTOR: Record<CityFilters["period"], number> = { "7d": 1, "30d": 4.3, "90d": 12.9, "12m": 52 };
const MODE_FACTOR: Record<CityFilters["mode"], number> = { all: 1, bike: 0.82, run: 0.18 };

function scaleKpi(k: Kpi, f: CityFilters): Kpi {
  if (k.id === "rides") {
    const v = Math.round(k.value * PERIOD_FACTOR[f.period] * MODE_FACTOR[f.mode]);
    return { ...k, value: v, unit: f.period === "7d" ? "this week" : `last ${f.period}`, spark: k.spark.map((x) => Math.round(x * PERIOD_FACTOR[f.period] * MODE_FACTOR[f.mode])) };
  }
  if (k.id === "pm25" && f.mode === "run") return { ...k, value: 11.6, spark: k.spark.map((x) => Math.round(x * 0.82 * 10) / 10) };
  return k;
}

function filterDistricts<T extends { district?: string; name?: string }>(rows: T[], f: CityFilters, key: "district" | "name" = "district") {
  if (!f.districts.length) return rows;
  return rows.filter((r) => f.districts.includes(String(r[key])));
}

const DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

function shiftedGeneratedAt(iso: string) {
  return new Date(new Date(iso).getTime() + (mockNow().getTime() - MOCK_ANCHOR_MS)).toISOString();
}

/** What changed: the few signals a mobility team should look at first. */
function cityAlerts(airNoise: AirNoiseCell[][], hotspots: BrakeHotspot[], ranking: SurfaceRankRow[]): CityAlert[] {
  const rising = [...hotspots].sort((a, b) => b.trend - a.trend)[0];
  const easing = [...hotspots].filter((h) => h.hardBrakesWeek >= 15).sort((a, b) => a.trend - b.trend)[0];
  const rough = [...ranking].filter((r) => r.surfaceIndex < 35).sort((a, b) => b.riders30d - a.riders30d)[0];
  let peak = { d: 0, h: 0, v: 0 };
  airNoise.forEach((row, d) => row.forEach((cell, h) => cell.pm25 > peak.v && (peak = { d, h, v: cell.pm25 })));
  const hh = (h: number) => `${String(h).padStart(2, "0")}:00`;
  const alerts: CityAlert[] = [];
  if (rising)
    alerts.push({
      id: "rising",
      tone: "bad",
      title: `Hard brakes rising at ${rising.label}`,
      body: `+${rising.trend}% vs the previous 30 days · ${rising.hardBrakesWeek} this week, mostly around ${hh(rising.peakHour)}.`,
      href: "/city/safety",
    });
  if (rough)
    alerts.push({
      id: "rough",
      tone: "bad",
      title: `${rough.street}${rough.from && rough.to ? ` (${rough.from} → ${rough.to})` : ""} needs resurfacing`,
      body: `Surface index ${rough.surfaceIndex}/100 on a street ${rough.riders30d.toLocaleString("en-US")} riders used this month; ${rough.confirmedImpacts} impacts confirmed.`,
      href: "/city/surface",
    });
  alerts.push({
    id: "air",
    tone: "mid",
    title: `PM2.5 peaks on ${DAY_NAMES[peak.d]}s at ${hh(peak.h)}`,
    body: `${peak.v.toFixed(1)} µg/m³ on measured streets, ${(peak.v / 10 - 1) * 100 > 0 ? `${Math.round((peak.v / 10 - 1) * 100)}% above` : "within"} the EU 2030 limit.`,
    href: "/city/air-noise",
  });
  if (easing && easing.trend < 0)
    alerts.push({
      id: "easing",
      tone: "good",
      title: `Fewer hard brakes at ${easing.label}`,
      body: `${easing.trend}% vs the previous 30 days since the signal phasing changed. Keep an eye on the parallel streets.`,
      href: "/city/safety",
    });
  return alerts;
}

/** GET /v1/city/overview?period=&districts=&mode= — KPIs aggregated over the selected districts. */
export function getCityOverview(f: CityFilters): Promise<CityOverview> {
  return endpoint(`/v1/city/overview?period=${f.period}&mode=${f.mode}`, async () => {
    const [c, hotspots, ranking, districtOf] = await Promise.all([loadCity(), loadHotspots(), loadSurfaceRanking(), hotspotDistricts()]);
    if (isSimulatingEmpty()) return { kpis: [], districts: [], alerts: [], generatedAt: shiftedGeneratedAt(c.generatedAt) };
    const active = hotspots.filter((h) => h.hardBrakesWeek >= ACTIVE_HOTSPOT_PER_WEEK);
    const districts: DistrictStat[] = c.districts.map((d) => ({
      ...d,
      ridesWeek: Math.round(d.ridesWeek * PERIOD_FACTOR[f.period] * MODE_FACTOR[f.mode]),
      hotspots: active.filter((h) => districtOf.get(h.id) === d.name).length,
    }));
    const selected = filterDistricts(districts, f, "name");
    let kpis = c.kpis.map((k) => scaleKpi(k, f));
    if (f.districts.length && selected.length) {
      // Re-aggregate the headline figures over the selected districts.
      const km = selected.reduce((s, d) => s + d.kmMeasured, 0);
      const allKm = districts.reduce((s, d) => s + d.kmMeasured, 0) || 1;
      const weighted = (get: (d: DistrictStat) => number) => selected.reduce((s, d) => s + get(d) * d.kmMeasured, 0) / (km || 1);
      const next: Record<string, number> = {
        km: Math.round(km * 10) / 10,
        rides: selected.reduce((s, d) => s + d.ridesWeek, 0),
        surface: Math.round(weighted((d) => d.surfaceIndex) * 10) / 10,
        hotspots: selected.reduce((s, d) => s + d.hotspots, 0),
        pm25: Math.round(weighted((d) => d.pm25) * 10) / 10,
      };
      kpis = kpis.map((k) => {
        if (!(k.id in next)) return k;
        const ratio = k.value ? next[k.id] / k.value : km / allKm;
        return { ...k, value: next[k.id], spark: k.spark.map((x) => Math.round(x * ratio * 10) / 10) };
      });
    }
    // Every district is returned (maps need the whole city); the UI highlights the selection.
    return { kpis, districts, alerts: cityAlerts(c.airNoise, hotspots, ranking), generatedAt: shiftedGeneratedAt(c.generatedAt) };
  });
}

/** GET /v1/city/surface/ranking */
export function getSurfaceRanking(f: CityFilters): Promise<SurfaceRankRow[]> {
  return endpoint(`/v1/city/surface/ranking?period=${f.period}`, async () => {
    if (f.mode === "run" || isSimulatingEmpty()) return []; // runners don't measure surface vibration
    const rows = await loadSurfaceRanking();
    return filterDistricts(rows, f).map((r) => ({
      ...r,
      confirmedImpacts: Math.round(r.confirmedImpacts * Math.min(3, Math.sqrt(PERIOD_FACTOR[f.period] / 4.3))),
      riders30d: Math.round(r.riders30d * MODE_FACTOR[f.mode]),
    }));
  });
}

export interface SafetyData {
  hotspots: BrakeHotspot[];
  monthly: MonthlyBrakes[];
  totals: {
    hardBrakes: number;
    perThousandRides: number;
    /** Change of the per-1,000-rides rate vs the previous period, in %. */
    delta: number;
    /** Clusters with at least ACTIVE_HOTSPOT_PER_WEEK hard brakes a week. */
    activeHotspots: number;
    /** Share of all hard brakes that happen at a hotspot. */
    atHotspotsPct: number;
  };
}

/** A junction is an "active" hotspot from this many hard brakes a week. */
export const ACTIVE_HOTSPOT_PER_WEEK = 8;
/** city.json stores a sampled count; the city-wide total is ~4.2× (all riders, not only the panel). */
const MONTHLY_BRAKE_SCALE = 4.2;
const MONTHS_IN: Record<CityFilters["period"], number> = { "7d": 1 / 4.3, "30d": 1, "90d": 3, "12m": 12 };

/** District of each hotspot = district of the nearest measured street segment. */
async function hotspotDistricts() {
  return once2("hotspotDistricts", async () => {
    const [hotspots, streets] = await Promise.all([loadHotspots(), loadStreets()]);
    const out = new Map<string, string>();
    for (const h of hotspots) {
      let best = Infinity;
      let district = "";
      for (const s of streets) {
        for (const [x, y] of s.coordinates) {
          const d = (x - h.coordinates[0]) ** 2 + ((y - h.coordinates[1]) * 1.33) ** 2;
          if (d < best) {
            best = d;
            district = s.district;
          }
        }
      }
      out.set(h.id, district);
    }
    return out;
  });
}

const memo: Record<string, unknown> = {};
async function once2<T>(key: string, load: () => Promise<T>): Promise<T> {
  if (!(key in memo)) memo[key] = await load();
  return memo[key] as T;
}

/** GET /v1/city/safety */
export function getCitySafety(f: CityFilters): Promise<SafetyData> {
  return endpoint(`/v1/city/safety?period=${f.period}`, async () => {
    const [hotspots, c, districtOf] = await Promise.all([loadHotspots(), loadCity(), hotspotDistricts()]);
    if (isSimulatingEmpty()) return { hotspots: [], monthly: [], totals: { hardBrakes: 0, perThousandRides: 0, delta: 0, activeHotspots: 0, atHotspotsPct: 0 } };
    const run = f.mode === "run";
    const modeBrakes = run ? 0.05 : f.mode === "bike" ? 0.97 : 1;
    const modeRides = MODE_FACTOR[f.mode];
    const share = f.districts.length ? hotspots.filter((h) => f.districts.includes(districtOf.get(h.id) ?? "")).length / hotspots.length : 1;

    const monthly = c.monthlyHardBrakes.map((m) => ({
      ...m,
      hardBrakes: Math.round(m.hardBrakes * MONTHLY_BRAKE_SCALE * modeBrakes * share),
      rides: Math.round(m.rides * modeRides * (f.districts.length ? Math.max(0.08, share) : 1)),
    }));
    // Totals over the selected period, and the same window just before it.
    const window = (end: number, months: number) => {
      const whole = Math.max(1, Math.ceil(months));
      const slice = monthly.slice(Math.max(0, end - whole), end);
      const k = months / whole;
      return { brakes: slice.reduce((s, m) => s + m.hardBrakes, 0) * k, rides: slice.reduce((s, m) => s + m.rides, 0) * k };
    };
    const months = MONTHS_IN[f.period];
    const now = window(monthly.length, months);
    const prev = window(monthly.length - Math.max(1, Math.ceil(months)), months);
    const rate = (w: { brakes: number; rides: number }) => (w.rides ? (w.brakes / w.rides) * 1000 : 0);

    const factor = (PERIOD_FACTOR[f.period] / 4.3) * modeBrakes;
    const list = hotspots
      .filter((h) => !f.districts.length || f.districts.includes(districtOf.get(h.id) ?? ""))
      .map((h) => ({ ...h, hardBrakes30d: Math.max(1, Math.round(h.hardBrakes30d * factor)), hardBrakesWeek: Math.max(run ? 0 : 1, Math.round(h.hardBrakesWeek * modeBrakes)) }));
    const atHotspots = list.reduce((s, h) => s + h.hardBrakes30d, 0);
    const total = Math.max(Math.round(now.brakes), atHotspots);
    return {
      hotspots: list,
      monthly,
      totals: {
        hardBrakes: total,
        perThousandRides: Math.round(rate(now) * 10) / 10,
        delta: prev.rides && rate(prev) ? Math.round(((rate(now) - rate(prev)) / rate(prev)) * 1000) / 10 : 0,
        activeHotspots: list.filter((h) => h.hardBrakesWeek >= ACTIVE_HOTSPOT_PER_WEEK).length,
        atHotspotsPct: total ? Math.round((atHotspots / total) * 100) : 0,
      },
    };
  });
}

/** GET /v1/city/air-noise?period= — hour × weekday matrix (Mon..Sun). */
export function getAirNoise(f: CityFilters): Promise<AirNoiseCell[][]> {
  return endpoint(`/v1/city/air-noise?period=${f.period}`, async () => {
    const c = await loadCity();
    if (isSimulatingEmpty()) return [];
    const seasonal = f.period === "12m" ? 1.04 : f.period === "90d" ? 0.97 : 1;
    const district = f.districts.length ? 1 + (f.districts.includes("Eixample") ? 0.08 : -0.04) : 1;
    return c.airNoise.map((row) =>
      row.map((cell) => ({
        pm25: Math.round(cell.pm25 * seasonal * district * 10) / 10,
        db: Math.round((cell.db + (district > 1 ? 1.2 : 0)) * 10) / 10,
        rides: Math.round(cell.rides * MODE_FACTOR[f.mode] * PERIOD_FACTOR[f.period]),
      })),
    );
  });
}

export interface ApiUsage {
  key: string;
  plan: string;
  quota: { used: number; limit: number; resetsAt: string };
  rateLimit: string;
  endpoints: { method: "GET" | "POST"; path: string; description: string }[];
  daily: { day: string; calls: number }[];
}

/** GET /v1/account/usage */
export function getApiUsage(): Promise<ApiUsage> {
  return endpoint("/v1/account/usage", () => {
    const now = mockNow();
    const daily = Array.from({ length: 14 }, (_, i) => {
      const d = new Date(now.getTime() - (13 - i) * 86_400_000);
      const weekend = [0, 6].includes(d.getUTCDay());
      return { day: d.toISOString().slice(0, 10), calls: Math.round((weekend ? 2100 : 5400) + Math.sin(i * 1.7) * 900 + i * 60) };
    });
    return {
      key: "umi_live_bcn_9f2c4e7a1d6b8e03c5a7",
      plan: "City pilot · Ajuntament de Barcelona",
      quota: { used: daily.reduce((s, d) => s + d.calls, 0) + 41_280, limit: 250_000, resetsAt: new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 1)).toISOString() },
      rateLimit: "20 requests / second",
      endpoints: [
        { method: "GET", path: "/v1/city/segments", description: "Scored street segments (GeoJSON), filterable by bbox, hour and mode" },
        { method: "GET", path: "/v1/city/surface/ranking", description: "Segments ranked by surface index, with confirmed impacts" },
        { method: "GET", path: "/v1/city/safety/hotspots", description: "Hard-brake clusters (> 3 m/s²) with counts and peak hours" },
        { method: "GET", path: "/v1/city/air-noise", description: "PM2.5 and dB(A) by hour × weekday" },
        { method: "GET", path: "/v1/city/districts", description: "District aggregates and boundaries" },
      ],
      daily,
    };
  });
}
