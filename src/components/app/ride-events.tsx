import { AlertTriangle, AudioLines, CircleDot, Wind, type LucideIcon } from "lucide-react";
import type { RideEventType } from "@/lib/types";

export const EVENT_META: Record<RideEventType, { label: string; unit: string; color: string; icon: LucideIcon; explain: string }> = {
  hard_brake: { label: "Hard brake", unit: "m/s²", color: "#ff5b1f", icon: AlertTriangle, explain: "Deceleration above 3 m/s²" },
  pothole: { label: "Pothole", unit: "m/s² peak", color: "#f5c542", icon: CircleDot, explain: "Vertical impact from the surface" },
  pm_spike: { label: "PM2.5 spike", unit: "µg/m³", color: "#ff7a47", icon: Wind, explain: "Short burst of fine particles" },
  noise_peak: { label: "Noise peak", unit: "dB(A)", color: "#f5c542", icon: AudioLines, explain: "Sound level above 80 dB(A)" },
};
