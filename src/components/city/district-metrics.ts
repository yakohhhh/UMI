import { overallScore, scoreBand, type ScoreBand } from "@/lib/score";
import type { DistrictStat } from "@/lib/types";

export type DistrictMetric = "overall" | "surface" | "pm25" | "db" | "hotspots";

export interface DistrictMetricMeta {
  id: DistrictMetric;
  label: string;
  short: string;
  /** Sort direction where the first row is the one needing attention. */
  worstFirst: (a: DistrictStat, b: DistrictStat) => number;
  value: (d: DistrictStat) => number;
  format: (d: DistrictStat) => string;
  band: (d: DistrictStat) => ScoreBand;
  legend: Record<ScoreBand, string>;
}

const by = (f: (d: DistrictStat) => number, dir: 1 | -1) => (a: DistrictStat, b: DistrictStat) => (f(a) - f(b)) * dir;

export const DISTRICT_METRICS: Record<DistrictMetric, DistrictMetricMeta> = {
  overall: {
    id: "overall",
    label: "Overall street score",
    short: "Overall",
    value: (d) => overallScore(d.scores),
    format: (d) => String(overallScore(d.scores)),
    band: (d) => scoreBand(overallScore(d.scores)),
    worstFirst: by((d) => overallScore(d.scores), 1),
    legend: { good: "Calm 70+", mid: "Mixed 45–69", bad: "Stressful < 45" },
  },
  surface: {
    id: "surface",
    label: "Surface index",
    short: "Surface",
    value: (d) => d.surfaceIndex,
    format: (d) => d.surfaceIndex.toFixed(1),
    band: (d) => scoreBand(d.surfaceIndex),
    worstFirst: by((d) => d.surfaceIndex, 1),
    legend: { good: "Smooth 70+", mid: "Bumpy 45–69", bad: "Rough < 45" },
  },
  pm25: {
    id: "pm25",
    label: "PM2.5 on measured streets",
    short: "PM2.5",
    value: (d) => d.pm25,
    format: (d) => `${d.pm25.toFixed(1)} µg`,
    band: (d) => (d.pm25 <= 10 ? "good" : d.pm25 <= 15 ? "mid" : "bad"),
    worstFirst: by((d) => d.pm25, -1),
    legend: { good: "≤ 10 µg/m³ (EU 2030)", mid: "10–15", bad: "> 15 (WHO 24 h)" },
  },
  db: {
    id: "db",
    label: "Noise on measured streets",
    short: "Noise",
    value: (d) => d.db,
    format: (d) => `${d.db.toFixed(1)} dB`,
    band: (d) => (d.db <= 58 ? "good" : d.db <= 64 ? "mid" : "bad"),
    worstFirst: by((d) => d.db, -1),
    legend: { good: "≤ 58 dB(A)", mid: "58–64", bad: "> 64 dB(A)" },
  },
  hotspots: {
    id: "hotspots",
    label: "Hard-brake hotspots",
    short: "Hotspots",
    value: (d) => d.hotspots,
    format: (d) => String(d.hotspots),
    band: (d) => (d.hotspots <= 2 ? "good" : d.hotspots <= 9 ? "mid" : "bad"),
    worstFirst: by((d) => d.hotspots, -1),
    legend: { good: "0–2", mid: "3–9", bad: "10 or more" },
  },
};
