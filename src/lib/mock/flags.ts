import type { BrakeCause, CityHazard, RideFlag } from "../types";

/**
 * Hand-placed flags and answers on top of the generated rides (no regeneration
 * needed). Positions, times and streets are read from activity-details.json:
 * coordinates = route[samples[k][6]], time = start + samples[k][0].
 */
export const MOCK_FLAGS: Record<string, RideFlag[]> = {
  "laia-20261015-0752": [
    { id: "laia-20261015-0752-f0", sampleIndex: 60, coordinates: [2.1802, 41.40168], time: "08:02", street: "Avinguda Diagonal", kind: "roadworks", source: "voice", status: "verified", confirmations: 3, ridersWarned: 57 },
    { id: "laia-20261015-0752-f1", sampleIndex: 86, coordinates: [2.19076, 41.4039], time: "08:07", street: "Carrer de la Llacuna", kind: null, source: "press", status: "pending", confirmations: 0, ridersWarned: 0 },
  ],
  "laia-20261007-1814": [
    { id: "laia-20261007-1814-f0", sampleIndex: 70, coordinates: [2.17058, 41.39863], time: "18:26", street: "Passeig de Sant Joan", kind: "danger", source: "press", status: "pending", confirmations: 1, ridersWarned: 0 },
  ],
  "laia-20261002-0738": [
    { id: "laia-20261002-0738-f0", sampleIndex: 40, coordinates: [2.17282, 41.39987], time: "07:45", street: "Avinguda Diagonal", kind: "blocked_lane", source: "voice", status: "sent_to_city", confirmations: 8, ridersWarned: 412 },
  ],
  "laia-20260926-1044": [
    {
      id: "laia-20260926-1044-f0",
      sampleIndex: 96,
      coordinates: [2.15766, 41.385],
      time: "11:00",
      street: "Carrer de Rocafort",
      kind: "pothole",
      source: "press",
      status: "fixed",
      confirmations: 11,
      ridersWarned: 640,
      proof: "Comfort on this block 52 → 81 since the repair",
    },
  ],
  "marc-20261014-0725": [
    {
      id: "marc-20261014-0725-f0",
      sampleIndex: 90,
      coordinates: [2.18244, 41.39275],
      time: "07:48",
      street: "Passeig de Lluís Companys",
      kind: "obstacle",
      source: "voice",
      status: "expired",
      confirmations: 2,
      ridersWarned: 38,
      proof: "Gone: 12 Clips passed without a swerve",
    },
  ],
};

/** Answers to "why did you brake?" by event id; `ask` marks the moments the app asks about. */
export const MOCK_BRAKE_ANSWERS: Record<string, { cause: BrakeCause | null; ask?: boolean }> = {
  "laia-20261015-0752-e0": { cause: null, ask: true },
  "laia-20261014-0754-e0": { cause: "animal", ask: true },
  "laia-20261013-0747-e0": { cause: "vehicle", ask: true },
  "laia-20261012-0754-e0": { cause: null },
  "laia-20261008-0758-e0": { cause: "just_me", ask: true },
  "laia-20261006-0746-e0": { cause: "vehicle" },
  "laia-20261002-0738-e0": { cause: "pedestrian", ask: true },
};

/** Flags that reached City Insights (5+ different riders). Laia's Diagonal and Rocafort flags are hz-2 and hz-5. */
export const MOCK_CITY_HAZARDS: CityHazard[] = [
  { id: "hz-1", kind: "blocked_lane", street: "Carrer de Girona (Consell de Cent → Diputació)", district: "Eixample", coordinates: [2.16975, 41.39602], riders: 23, firstSeen: "2026-09-14", lastConfirmed: "2026-10-15", status: "new" },
  { id: "hz-2", kind: "blocked_lane", street: "Avinguda Diagonal (Roger de Flor → Padilla)", district: "Eixample", coordinates: [2.17282, 41.39987], riders: 9, firstSeen: "2026-10-02", lastConfirmed: "2026-10-14", status: "sent_to_iris" },
  { id: "hz-3", kind: "roadworks", street: "Carrer de Pujades (Llacuna → Roc Boronat)", district: "Sant Martí", coordinates: [2.1926, 41.39904], riders: 14, firstSeen: "2026-10-06", lastConfirmed: "2026-10-15", status: "scheduled" },
  { id: "hz-4", kind: "pothole", street: "Gran Via de les Corts Catalanes", district: "Eixample", coordinates: [2.17495, 41.39443], riders: 16, firstSeen: "2026-10-11", lastConfirmed: "2026-10-15", status: "sent_to_iris" },
  { id: "hz-5", kind: "pothole", street: "Carrer de Rocafort", district: "Eixample", coordinates: [2.15841, 41.38556], riders: 12, firstSeen: "2026-09-26", lastConfirmed: "2026-10-09", status: "fixed" },
  { id: "hz-6", kind: "danger", street: "Pg. de Sant Joan × Gran Via (Tetuan)", district: "Eixample", coordinates: [2.17555, 41.39488], riders: 17, firstSeen: "2026-09-21", lastConfirmed: "2026-10-15", status: "new" },
  { id: "hz-7", kind: "roadworks", street: "Carrer de Llull (Badajoz → Llacuna)", district: "Sant Martí", coordinates: [2.19265, 41.3973], riders: 6, firstSeen: "2026-10-13", lastConfirmed: "2026-10-15", status: "new" },
];
