import type { MapMetric, ScoreDimension, Scores } from "./types";

/** Score bands: blue = calm / good, yellow = average, orange = poor. */
export type ScoreBand = "good" | "mid" | "bad";

export const BAND_THRESHOLDS = { good: 70, mid: 45 } as const;

export function scoreBand(score: number): ScoreBand {
  if (score >= BAND_THRESHOLDS.good) return "good";
  if (score >= BAND_THRESHOLDS.mid) return "mid";
  return "bad";
}

export interface DimensionMeta {
  id: MapMetric;
  label: string;
  short: string;
  question: string;
  measures: string;
  bands: Record<ScoreBand, string>;
}

export const DIMENSIONS: Record<MapMetric, DimensionMeta> = {
  comfort: {
    id: "comfort",
    label: "Comfort",
    short: "CMF",
    question: "How smooth is the surface?",
    measures: "Vibration (m/s² RMS) from the 6-axis IMU",
    bands: { good: "Smooth", mid: "Bumpy", bad: "Rough" },
  },
  safety: {
    id: "safety",
    label: "Safety",
    short: "SFT",
    question: "How often do riders brake hard?",
    measures: "Hard brakes > 3 m/s² and impacts",
    bands: { good: "Calm", mid: "Watch out", bad: "Tense" },
  },
  air: {
    id: "air",
    label: "Air",
    short: "AIR",
    question: "What are you breathing?",
    measures: "PM2.5 (µg/m³), laser particle sensor",
    bands: { good: "Clean", mid: "Moderate", bad: "Polluted" },
  },
  noise: {
    id: "noise",
    label: "Noise",
    short: "NSE",
    question: "How loud is the street?",
    measures: "Sound level dB(A), MEMS microphone",
    bands: { good: "Quiet", mid: "Busy", bad: "Loud" },
  },
  overall: {
    id: "overall",
    label: "Overall",
    short: "ALL",
    question: "How does the street feel overall?",
    measures: "Weighted mix of the four scores, pulled toward the weakest",
    bands: { good: "Calm", mid: "Mixed", bad: "Stressful" },
  },
};

export const SCORE_DIMENSIONS: ScoreDimension[] = ["comfort", "safety", "air", "noise"];

export function bandLabel(score: number, metric: MapMetric = "overall") {
  return DIMENSIONS[metric].bands[scoreBand(score)];
}

/**
 * Overall street score. A street is only as calm as its worst aspect, so the
 * weighted mean (comfort & safety weigh a bit more for riders) is pulled toward
 * the weakest dimension, then calibrated so 50 sits at the city's rush-hour
 * median — the same spread as the four sub-scores.
 */
export function overallScore(s: Scores) {
  const mean = s.comfort * 0.3 + s.safety * 0.3 + s.air * 0.2 + s.noise * 0.2;
  const weakest = Math.min(s.comfort, s.safety, s.air, s.noise);
  const raw = 0.55 * mean + 0.45 * weakest;
  const v = 50 + (raw - 52) * 1.5;
  // soft knees keep the extremes believable (no street is a perfect 100)
  const kneed = v > 80 ? 80 + (v - 80) * 0.5 : v < 20 ? 20 - (20 - v) * 0.5 : v;
  return clamp(Math.round(kneed));
}

export function metricValue(s: Scores, metric: MapMetric) {
  return metric === "overall" ? overallScore(s) : s[metric];
}

/** Fill colours (charts, map lines, dots). Same hue family in both themes. */
export const BAND_COLORS: Record<"dark" | "light", Record<ScoreBand, string>> = {
  dark: { good: "#3d9bff", mid: "#f5c542", bad: "#ff5b1f" },
  light: { good: "#2f8bff", mid: "#e9b21c", bad: "#f2541b" },
};

export function scoreColor(score: number, theme: "dark" | "light" = "dark") {
  return BAND_COLORS[theme][scoreBand(score)];
}

/** CSS custom-property versions, for components that follow the theme. */
export const BAND_VAR: Record<ScoreBand, { fill: string; ink: string }> = {
  good: { fill: "var(--good-fill)", ink: "var(--good)" },
  mid: { fill: "var(--mid-fill)", ink: "var(--mid)" },
  bad: { fill: "var(--bad-fill)", ink: "var(--bad)" },
};

// Conversions used by the sensors (kept in sync with scripts/generate-mock-data.mjs).
export const airScoreFromPm = (pm: number) => clamp(Math.round(100 - (pm - 5) * 3.2));
export const noiseScoreFromDb = (db: number) => clamp(Math.round(100 - (db - 50) * 3.3));
export const comfortScoreFromVib = (vib: number) => clamp(Math.round(100 - (vib - 0.4) * 38));
export const pmFromAirScore = (score: number) => Math.round((5 + (100 - score) / 3.2) * 10) / 10;
export const dbFromNoiseScore = (score: number) => Math.round(50 + (100 - score) / 3.3);
export const vibFromComfortScore = (score: number) => Math.round((0.4 + (100 - score) / 38) * 100) / 100;
/** Hard brakes (> 3 m/s²) per 100 passes implied by a safety score. */
export const brakesFromSafetyScore = (score: number) => Math.max(0, Math.round((100 - score) / 4.5));

function clamp(v: number) {
  return Math.max(0, Math.min(100, v));
}

/** MapLibre expression colouring a numeric property with the score scale. */
export function scoreColorExpression(property: unknown, theme: "dark" | "light" = "dark") {
  const c = BAND_COLORS[theme];
  return ["step", property, c.bad, BAND_THRESHOLDS.mid, c.mid, BAND_THRESHOLDS.good, c.good] as const;
}
