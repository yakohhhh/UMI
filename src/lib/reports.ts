import type { ActivitySummary, BrakeCause, CauseBucket, HazardKind } from "./types";

/**
 * Rules for rider flags and "why did you brake?" answers, shared by the rider
 * app and City Insights.
 *
 * A hard brake is a measured fact; its cause is context. A dog crossing is not
 * a false positive: it still counts for the junction, it just gets a reason.
 * Only "just me" leaves street data, and it stays in the rider's own report.
 */

/** Different riders before a flag shows on everyone's street map (same rule as potholes). */
export const MAP_MIN_RIDERS = 3;
/** Different riders before a flag or a cause mix reaches City Insights (k-anonymity, like every city figure). */
export const CITY_MIN_RIDERS = 5;
/** Moments the app asks about after a ride, at most. */
export const MAX_QUESTIONS_PER_RIDE = 2;

export const CAUSE_BUCKET: Record<BrakeCause, CauseBucket> = {
  pedestrian: "behaviour",
  animal: "behaviour",
  vehicle: "behaviour",
  car_door: "behaviour",
  lane_blocked: "infrastructure",
  surface: "infrastructure",
  roadworks: "infrastructure",
  junction: "infrastructure",
  just_me: "personal",
};

/** Weight of a hard brake in a junction's safety score, by what we know about its cause. */
export function brakeWeight(cause: BrakeCause | null | undefined) {
  if (cause === undefined || cause === null) return 0.5;
  return CAUSE_BUCKET[cause] === "personal" ? 0 : 1;
}

/** How long a flag stays live without a new confirmation. */
export const HAZARD_LIFETIME: Record<HazardKind, string> = {
  obstacle: "2 h unless riders confirm it again",
  roadworks: "until riders say it's gone · re-checked after 14 days",
  pothole: "until the Clips stop feeling the impact",
  blocked_lane: "a pattern by time of day, fades after 30 days",
  danger: "joins the junction's safety score, fades after 30 days",
};

/** Moments left to answer on a ride: unanswered asked brakes, then flags pressed without a keyword. */
export function momentsToCheck(a: Pick<ActivitySummary, "events" | "flags">) {
  return a.events.filter((e) => e.ask && !e.cause).length + a.flags.filter((f) => !f.kind).length;
}
