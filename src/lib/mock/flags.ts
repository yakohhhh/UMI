import type { BrakeCause, CityHazard, RideFlag } from "../types";
import data from "./data/flags.json";

/**
 * Hand-placed flags and answers on top of the generated rides (no regeneration
 * needed). The values live in data/flags.json so the backend seed reads the
 * same file. Positions, times and streets are read from activity-details.json:
 * coordinates = route[samples[k][6]], time = start + samples[k][0].
 * `flagHazards` in the JSON links a flag to the city hazard it joined; only the
 * backend seed needs it.
 */
interface FlagsData {
  flags: Record<string, RideFlag[]>;
  brakeAnswers: Record<string, { cause: BrakeCause | null; ask?: boolean }>;
  cityHazards: CityHazard[];
}

// JSON imports widen string unions to `string`; the cast restores the domain types.
const typed = data as unknown as FlagsData;

/** Flags pressed during each ride, by activity id. */
export const MOCK_FLAGS: Record<string, RideFlag[]> = typed.flags;

/** Answers to "why did you brake?" by event id; `ask` marks the moments the app asks about. */
export const MOCK_BRAKE_ANSWERS: FlagsData["brakeAnswers"] = typed.brakeAnswers;

/** Flags that reached City Insights (5+ different riders). Laia's Diagonal and Rocafort flags are hz-2 and hz-5. */
export const MOCK_CITY_HAZARDS: CityHazard[] = typed.cityHazards;
