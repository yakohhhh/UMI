"use client";

import { motion, useInView, useReducedMotion } from "framer-motion";
import { useRef } from "react";
import { BAND_VAR, DIMENSIONS, scoreBand } from "@/lib/score";
import type { MapMetric } from "@/lib/types";
import { cn } from "@/lib/utils";
import { DimensionIcon } from "./dimension-icon";

const ARC = 300 / 360; // gauge sweep, gap at the bottom

/** Large circular gauge with an animated arc. Announced as a meter. */
export function ScoreGauge({
  metric,
  score,
  size = 132,
  stroke = 10,
  caption,
  className,
}: {
  metric: MapMetric;
  score: number;
  size?: number;
  stroke?: number;
  caption?: string;
  className?: string;
}) {
  const ref = useRef<SVGSVGElement>(null);
  const inView = useInView(ref, { once: true, margin: "-40px" });
  const reduce = useReducedMotion();
  const band = scoreBand(score);
  const meta = DIMENSIONS[metric];
  const r = (size - stroke) / 2;
  const c = size / 2;
  const shown = reduce || inView;

  return (
    <figure className={cn("flex flex-col items-center gap-2", className)}>
      <div className="relative" style={{ width: size, height: size }}>
        <svg
          ref={ref}
          width={size}
          height={size}
          viewBox={`0 0 ${size} ${size}`}
          role="meter"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={score}
          aria-label={`${meta.label} score ${score} out of 100, ${meta.bands[band]}`}
        >
          <circle
            cx={c}
            cy={c}
            r={r}
            fill="none"
            stroke="var(--surface-3)"
            strokeWidth={stroke}
            strokeLinecap="round"
            pathLength={1}
            strokeDasharray={`${ARC} 1`}
            transform={`rotate(120 ${c} ${c})`}
          />
          <motion.circle
            cx={c}
            cy={c}
            r={r}
            fill="none"
            stroke={BAND_VAR[band].fill}
            strokeWidth={stroke}
            strokeLinecap="round"
            transform={`rotate(120 ${c} ${c})`}
            initial={{ pathLength: reduce ? (ARC * score) / 100 : 0 }}
            animate={{ pathLength: shown ? (ARC * score) / 100 : 0 }}
            transition={{ duration: 1.1, ease: [0.16, 1, 0.3, 1], delay: 0.1 }}
          />
        </svg>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center" aria-hidden>
          <span className="font-num leading-none font-semibold text-fg" style={{ fontSize: size * 0.27 }}>
            {score}
          </span>
          <span className="mt-1 text-[11px] font-medium" style={{ color: BAND_VAR[band].ink }}>
            {meta.bands[band]}
          </span>
        </div>
      </div>
      <figcaption className="flex items-center gap-1.5 text-[13px] font-medium text-fg">
        <DimensionIcon metric={metric} className="size-4 text-fg-muted" />
        {meta.label}
        {caption ? <span className="font-normal text-fg-subtle">· {caption}</span> : null}
      </figcaption>
    </figure>
  );
}

/** Small ring used inside lists and the phone mock-up. */
export function ScoreRing({ score, size = 40, stroke = 4, className, label }: { score: number; size?: number; stroke?: number; className?: string; label?: string }) {
  const band = scoreBand(score);
  const r = (size - stroke) / 2;
  const c = size / 2;
  return (
    <span className={cn("relative inline-flex items-center justify-center", className)} style={{ width: size, height: size }} aria-label={label ?? `Score ${score}`} role="img">
      <svg width={size} height={size} aria-hidden>
        <circle cx={c} cy={c} r={r} fill="none" stroke="var(--surface-3)" strokeWidth={stroke} />
        <circle
          cx={c}
          cy={c}
          r={r}
          fill="none"
          stroke={BAND_VAR[band].fill}
          strokeWidth={stroke}
          strokeLinecap="round"
          pathLength={1}
          strokeDasharray={`${score / 100} 1`}
          transform={`rotate(-90 ${c} ${c})`}
        />
      </svg>
      <span className="absolute font-num text-[11px] font-semibold text-fg" style={{ fontSize: size * 0.3 }} aria-hidden>
        {score}
      </span>
    </span>
  );
}
