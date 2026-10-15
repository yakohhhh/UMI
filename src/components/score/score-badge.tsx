import { DIMENSIONS, BAND_VAR, scoreBand } from "@/lib/score";
import type { MapMetric } from "@/lib/types";
import { cn } from "@/lib/utils";
import { DimensionIcon } from "./dimension-icon";

type Variant = "solid" | "soft" | "dot";

/**
 * Score pill. Colour is always paired with the number (and the label on hover
 * / for screen readers) — never colour alone.
 */
export function ScoreBadge({
  metric,
  score,
  variant = "soft",
  showLabel = false,
  showIcon = true,
  size = "md",
  className,
}: {
  metric: MapMetric;
  score: number;
  variant?: Variant;
  showLabel?: boolean;
  showIcon?: boolean;
  size?: "sm" | "md";
  className?: string;
}) {
  const band = scoreBand(score);
  const meta = DIMENSIONS[metric];
  const aria = `${meta.label} ${score} out of 100, ${meta.bands[band]}`;
  const colors = BAND_VAR[band];
  return (
    <span
      aria-label={aria}
      title={aria}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full font-medium whitespace-nowrap tabular-nums",
        size === "sm" ? "h-6 px-2 text-[11px]" : "h-7 px-2.5 text-xs",
        variant === "solid" && "text-asphalt-900",
        variant === "soft" && "border",
        variant === "dot" && "px-0",
        className,
      )}
      style={
        variant === "solid"
          ? { background: colors.fill }
          : variant === "soft"
            ? { background: `color-mix(in srgb, ${colors.fill} 13%, transparent)`, borderColor: `color-mix(in srgb, ${colors.fill} 32%, transparent)`, color: colors.ink }
            : undefined
      }
    >
      {variant === "dot" ? <span aria-hidden className="size-2 rounded-full" style={{ background: colors.fill }} /> : null}
      {showIcon && variant !== "dot" ? <DimensionIcon metric={metric} className={size === "sm" ? "size-3" : "size-3.5"} strokeWidth={2.2} /> : null}
      {showLabel ? <span className={cn(variant === "dot" && "text-fg-muted")}>{meta.label}</span> : null}
      <span className={cn("font-num font-semibold", variant === "dot" && "text-fg")} aria-hidden>
        {score}
      </span>
    </span>
  );
}

/** The four scores of a ride, compact. */
export function ScorePills({ scores, size = "sm", className }: { scores: Record<"comfort" | "safety" | "air" | "noise", number>; size?: "sm" | "md"; className?: string }) {
  return (
    <div className={cn("flex flex-wrap items-center gap-1.5", className)}>
      {(["comfort", "safety", "air", "noise"] as const).map((m) => (
        <ScoreBadge key={m} metric={m} score={scores[m]} size={size} showLabel={size === "md"} />
      ))}
    </div>
  );
}

export function ScoreLegend({ metric = "overall", className, compact }: { metric?: MapMetric; className?: string; compact?: boolean }) {
  const meta = DIMENSIONS[metric];
  const items = [
    { band: "good" as const, range: "70–100" },
    { band: "mid" as const, range: "45–69" },
    { band: "bad" as const, range: "0–44" },
  ];
  return (
    <ul className={cn("flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-fg-muted", className)} aria-label={`${meta.label} score legend`}>
      {items.map((i) => (
        <li key={i.band} className="inline-flex items-center gap-1.5">
          <span aria-hidden className="h-1.5 w-4 rounded-full" style={{ background: BAND_VAR[i.band].fill }} />
          <span className="font-medium text-fg">{meta.bands[i.band]}</span>
          {!compact && <span className="font-mono text-[11px] text-fg-subtle">{i.range}</span>}
        </li>
      ))}
    </ul>
  );
}

export function ScoreDot({ score, className }: { score: number; className?: string }) {
  return <span aria-hidden className={cn("inline-block size-2 rounded-full", className)} style={{ background: BAND_VAR[scoreBand(score)].fill }} />;
}
