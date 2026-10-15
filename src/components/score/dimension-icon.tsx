import { AudioLines, Gauge, ShieldCheck, Waves, Wind, type LucideProps } from "lucide-react";
import type { MapMetric } from "@/lib/types";

const ICONS = { comfort: Waves, safety: ShieldCheck, air: Wind, noise: AudioLines, overall: Gauge } as const;

export function DimensionIcon({ metric, ...props }: { metric: MapMetric } & LucideProps) {
  const Icon = ICONS[metric];
  return <Icon aria-hidden="true" {...props} />;
}
