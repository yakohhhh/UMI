import {
  AlertTriangle,
  AudioLines,
  CarFront,
  CircleCheckBig,
  CircleDot,
  Construction,
  Dog,
  DoorOpen,
  Hand,
  Hourglass,
  Landmark,
  Mic,
  OctagonAlert,
  PersonStanding,
  Signpost,
  TrafficCone,
  TriangleAlert,
  Users,
  Wind,
  type LucideIcon,
} from "lucide-react";
import type { BrakeCause, CauseBucket, FlagSource, FlagStatus, HazardKind, RideEventType, RideFlag } from "@/lib/types";

export const EVENT_META: Record<RideEventType, { label: string; unit: string; color: string; icon: LucideIcon; explain: string }> = {
  hard_brake: { label: "Hard brake", unit: "m/s²", color: "#ff5b1f", icon: AlertTriangle, explain: "Deceleration above 3 m/s²" },
  pothole: { label: "Pothole", unit: "m/s² peak", color: "#f5c542", icon: CircleDot, explain: "Vertical impact from the surface" },
  pm_spike: { label: "PM2.5 spike", unit: "µg/m³", color: "#ff7a47", icon: Wind, explain: "Short burst of fine particles" },
  noise_peak: { label: "Noise peak", unit: "dB(A)", color: "#f5c542", icon: AudioLines, explain: "Sound level above 80 dB(A)" },
};

/** Answers to "why did you brake?", in the order they are offered. */
export const CAUSE_META: Record<BrakeCause, { label: string; icon: LucideIcon }> = {
  vehicle: { label: "A vehicle cut across", icon: CarFront },
  pedestrian: { label: "Someone stepped out", icon: PersonStanding },
  animal: { label: "An animal", icon: Dog },
  car_door: { label: "Car door", icon: DoorOpen },
  lane_blocked: { label: "Lane blocked", icon: TrafficCone },
  junction: { label: "Junction or light", icon: Signpost },
  surface: { label: "Road surface", icon: CircleDot },
  roadworks: { label: "Roadworks", icon: Construction },
  just_me: { label: "Just me", icon: Hand },
};

export const BUCKET_META: Record<CauseBucket, { label: string; detail: string }> = {
  infrastructure: { label: "Street issue", detail: "Goes to the city's maintenance list once 5 riders agree" },
  behaviour: { label: "Traffic", detail: "Still counts for this junction's safety score, with its reason" },
  personal: { label: "Just you", detail: "Kept in your ride, left out of street scores and city data" },
};

/** What a flag is about. Keywords are the words the Clip listens for while the button is held. */
export const HAZARD_META: Record<HazardKind, { label: string; icon: LucideIcon; color: string; keywords: string }> = {
  roadworks: { label: "Roadworks", icon: Construction, color: "#f5c542", keywords: "obres · obras · roadworks" },
  pothole: { label: "Pothole", icon: CircleDot, color: "#f5c542", keywords: "forat · bache · pothole" },
  blocked_lane: { label: "Blocked lane", icon: TrafficCone, color: "#ff7a47", keywords: "bloquejat · bloqueado · blocked" },
  obstacle: { label: "Obstacle", icon: OctagonAlert, color: "#ff7a47", keywords: "obstacle · obstáculo" },
  danger: { label: "Dangerous spot", icon: TriangleAlert, color: "#ff5b1f", keywords: "perill · peligro · danger" },
};

export const FLAG_SOURCE_LABEL: Record<FlagSource, { label: string; short: string; icon: LucideIcon }> = {
  press: { label: "Flagged with the button", short: "Button", icon: Hand },
  voice: { label: "Flagged by voice", short: "Voice", icon: Mic },
};

/** "4 riders, you included · 57 warned": riders always count the person who flagged, like the 3- and 5-rider rules. */
export function flagReach(f: RideFlag, own: boolean) {
  const riders = f.confirmations + 1;
  const who = riders === 1 ? (own ? "Only you so far" : "1 rider so far") : `${riders} riders${own ? ", you included" : ""}`;
  return f.ridersWarned ? `${who} · ${f.ridersWarned.toLocaleString("en-US")} warned` : who;
}

/** Status chips: an icon and a word, never colour alone. */
export const FLAG_STATUS_META: Record<FlagStatus, { label: string; icon: LucideIcon; tone: "neutral" | "lane" | "signal" | "good" }> = {
  pending: { label: "Waiting for riders", icon: Hourglass, tone: "neutral" },
  verified: { label: "Verified", icon: Users, tone: "lane" },
  sent_to_city: { label: "Sent to the city", icon: Landmark, tone: "signal" },
  fixed: { label: "Fixed", icon: CircleCheckBig, tone: "good" },
  expired: { label: "Gone", icon: CircleCheckBig, tone: "neutral" },
};
