import type { FeatureCollection, Geometry } from "geojson";

/**
 * Domain models shared by the rider app and City Insights.
 * Shapes mirror the planned REST API (FastAPI) so mocks can be swapped 1:1.
 */

export type LngLat = [number, number];

export type ScoreDimension = "comfort" | "safety" | "air" | "noise";
export type MapMetric = ScoreDimension | "overall";

export interface Scores {
  comfort: number;
  safety: number;
  air: number;
  noise: number;
}

export type HourlyScores = Record<ScoreDimension, number[]>; // 24 values, 0–100

export type StreetKind = "arterial" | "boulevard" | "street" | "green" | "promenade" | "seafront";

export interface StreetSegment {
  id: string;
  name: string;
  from: string | null;
  to: string | null;
  district: string;
  kind: StreetKind;
  bikeLane: boolean;
  lengthM: number;
  coordinates: LngLat[];
  scores: Scores;
  hourly: HourlyScores;
  passes30d: number;
  /** Change of the overall score vs the previous 30 days, in points. */
  trend: number;
  surface: { vibRms: number; potholes: number };
  /** Typical PM2.5 (µg/m³) and noise (dB(A)) measured on the segment. */
  pm25: number;
  db: number;
}

export type ActivityType = "ride" | "run";
export type RideEventType = "hard_brake" | "pothole" | "pm_spike" | "noise_peak";

export interface RideEvent {
  type: RideEventType;
  sampleIndex: number;
  coordinates: LngLat;
  /** m/s² for brakes, m/s² peak for potholes, µg/m³ for PM2.5, dB(A) for noise. */
  value: number;
  time: string; // HH:mm, Europe/Madrid
  street: string | null;
}

export interface ActivitySummary {
  id: string;
  athleteId: string;
  type: ActivityType;
  title: string;
  /** Human label for where the activity happened, e.g. "Gràcia → 22@". */
  place: string;
  description: string | null;
  startedAt: string; // ISO
  durationS: number;
  movingTimeS: number;
  distanceM: number;
  avgSpeedKmh: number;
  maxSpeedKmh: number;
  elevationGainM: number;
  scores: Scores;
  events: RideEvent[];
  /** Simplified trace for thumbnails. */
  preview: LngLat[];
  kudos: number;
  kudoedBy: string[];
  comments: number;
  featured: boolean;
  weather: { tempC: number; condition: string };
}

/** [t (s), distance (m), speed (km/h), vibration (m/s² RMS), PM2.5 (µg/m³), noise (dB), route index] */
export type ActivitySample = [number, number, number, number, number, number, number];

export interface ActivitySegment {
  segmentId: string;
  name: string;
  from: string | null;
  to: string | null;
  distanceM: number;
  score: number;
  streetAverage: number;
  bikeLane: boolean;
}

export interface ActivityDetail extends ActivitySummary {
  route: LngLat[];
  samples: ActivitySample[];
  segments: ActivitySegment[];
}

export interface Athlete {
  id: string;
  name: string;
  firstName: string;
  initials: string;
  age: number;
  city: string;
  vehicle: string;
}

export interface WeekStats {
  distanceKm: number;
  movingTimeS: number;
  rides: number;
  runs: number;
  goalKm: number;
  streakDays: number;
  /** Distance per day, Monday first. */
  days: { label: string; km: number; isToday: boolean }[];
}

export interface BestWindow {
  title: string;
  window: string;
  detail: string;
  metric: ScoreDimension;
  score: number;
}

export interface ClipStatus {
  name: string;
  serial: string;
  battery: number;
  lastSync: string; // ISO
  firmware: string;
  connected: boolean;
  sensors: { id: string; label: string; enabled: boolean; detail: string }[];
}

export interface PlannedRoute {
  id: string;
  goal: "fastest" | "calmest" | "cleanest";
  label: string;
  durationMin: number;
  distanceM: number;
  scores: Scores;
  via: string[];
  highlight: string;
  coordinates: LngLat[];
}

export interface Pothole {
  id: string;
  segmentId: string;
  street: string;
  coordinates: LngLat;
  confirmations: number;
  firstSeen: string;
  severity: "low" | "medium" | "high";
}

export interface BrakeHotspot {
  id: string;
  label: string;
  coordinates: LngLat;
  hardBrakesWeek: number;
  hardBrakes30d: number;
  peakHour: number;
  trend: number;
  avgDecel: number;
}

export interface ExposureDay {
  date: string; // YYYY-MM-DD
  rideMin: number;
  pm25: number | null;
  db: number | null;
  doseUgH: number;
}

export interface ExposurePeriod {
  label: string;
  start: string;
  pm25: number | null;
  db: number | null;
  rideMin: number;
}

export interface ExposureSummary {
  days: ExposureDay[];
  weekly: ExposurePeriod[];
  monthly: ExposurePeriod[];
  thresholds: { whoPm25Annual: number; whoPm25Daily: number; eu2030Pm25: number; whoRoadNoise: number };
  insights: { id: string; tone: "good" | "neutral" | "watch"; title: string; body: string }[];
  totals: { avgPm25: number; avgDb: number; rideHours: number; changePct: number; ridingDays: number; dbChange: number };
  /** Streets that contribute most to the rider's PM2.5 dose (last 90 days). */
  contributors: { street: string; share: number; pm25: number; minutesWeek: number }[];
}

export interface ProfileStats {
  totals: { distanceKm: number; rides: number; runs: number; hours: number; streetsMapped: number; since: string };
  records: { id: string; label: string; value: string; detail: string; date: string }[];
  badges: { id: string; label: string; description: string; earned: boolean; progress?: number }[];
  contributions: { streetsImproved: number; potholesConfirmed: number; segmentsFirst: number; topStreets: { name: string; passes: number }[] };
  clubs: { id: string; name: string; challenge: string; progress: number; goal: number; unit: string; members: number }[];
}

// ------------------------------------------------------------------ City Insights

export type Period = "7d" | "30d" | "90d" | "12m";
export type ModeFilter = "all" | "bike" | "run";

export interface CityFilters {
  period: Period;
  districts: string[]; // empty = all
  mode: ModeFilter;
}

export interface Kpi {
  id: string;
  label: string;
  value: number;
  unit: string;
  delta: number;
  deltaUnit: string;
  /** What the delta compares against, e.g. "vs last winter" (default "vs prev."). */
  deltaLabel?: string;
  better: "up" | "down";
  spark: number[];
  limit?: number;
  limitLabel?: string;
}

export interface DistrictStat {
  name: string;
  code: string;
  scores: Scores;
  surfaceIndex: number;
  ridesWeek: number;
  kmMeasured: number;
  hotspots: number;
  pm25: number;
  db: number;
}

export interface SurfaceRankRow {
  segmentId: string;
  street: string;
  from: string | null;
  to: string | null;
  district: string;
  surfaceIndex: number;
  confirmedImpacts: number;
  riders30d: number;
  trend: number;
  lengthM: number;
}

export interface MonthlyBrakes {
  month: string;
  hardBrakes: number;
  rides: number;
}

export interface AirNoiseCell {
  pm25: number;
  db: number;
  rides: number;
}

export interface CityAlert {
  id: string;
  tone: "good" | "mid" | "bad";
  title: string;
  body: string;
  href: string;
}

export interface CityOverview {
  kpis: Kpi[];
  districts: DistrictStat[];
  alerts: CityAlert[];
  generatedAt: string;
}

export type GeoFeatureCollection<G extends Geometry = Geometry, P = Record<string, unknown>> = FeatureCollection<G, P>;
