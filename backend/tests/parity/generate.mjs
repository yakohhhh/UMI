// Records what the web app's mock API (src/lib/api.ts) answers at a fixed
// moment, so the backend tests can check they answer the same.
//
//   node --experimental-transform-types --no-warnings \
//     --import ./backend/tests/parity/hooks.mjs backend/tests/parity/generate.mjs
//
// Run from the repository root after changing the mocks or src/lib/api.ts.
import { writeFileSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";

const FROZEN_NOW = "2026-11-18T10:00:00.000Z";

const frozen = Date.parse(FROZEN_NOW);
Date.now = () => frozen;
// The mocks simulate network latency; there is nothing to wait for here.
globalThis.setTimeout = (callback) => {
  queueMicrotask(callback);
  return 0;
};

const root = new URL("../../../", import.meta.url);
const api = await import(pathToFileURL(fileURLToPath(new URL("src/lib/api.ts", root))).href);

const FILTERS = [
  { period: "30d", mode: "all", districts: [] },
  { period: "7d", mode: "bike", districts: ["Eixample"] },
  { period: "12m", mode: "run", districts: [] },
  { period: "90d", mode: "all", districts: ["Gràcia", "Sant Martí"] },
];
const ACTIVITIES = ["laia-20261015-0752", "laia-20260926-1044", "marc-20261014-0725"];
const DEPARTURES = [undefined, "07:00", "13:00", "22:00"];

const city = [];
for (const f of FILTERS) {
  city.push({
    filters: f,
    overview: await api.getCityOverview(f),
    surfaceRanking: await api.getSurfaceRanking(f),
    safety: await api.getCitySafety(f),
    hazards: await api.getCityHazards(f),
    airNoise: await api.getAirNoise(f),
  });
}

const fixture = {
  frozenNow: FROZEN_NOW,
  me: await api.getCurrentAthlete(),
  marc: await api.getAthlete("marc"),
  feed: await api.getFeed(),
  activities: Object.fromEntries(await Promise.all(ACTIVITIES.map(async (id) => [id, await api.getActivity(id)]))),
  week: await api.getWeekStats(),
  bestWindow: await api.getBestWindow(),
  clip: await api.getClipStatus(),
  potholes: await api.getPotholes(),
  hotspots: await api.getBrakeHotspots(),
  liveHazards: await api.getLiveHazards(),
  routes: await Promise.all(DEPARTURES.map(async (departAt) => ({ departAt: departAt ?? null, routes: await api.planRoutes({ from: "Gràcia", to: "22@", departAt }) }))),
  exposure: await api.getExposure(),
  profile: await api.getProfileStats(),
  usage: await api.getApiUsage(),
  city,
};

writeFileSync(new URL("mock-responses.json", import.meta.url), JSON.stringify(fixture) + "\n");
console.log("wrote backend/tests/parity/mock-responses.json");
