import { useId } from "react";
import { cn } from "@/lib/utils";

/** Tiny trend line. Decorative — the value it summarises is always shown next to it. */
export function Sparkline({
  data,
  className,
  color = "var(--color-signal)",
  height = 36,
  area = true,
}: {
  data: number[];
  className?: string;
  color?: string;
  height?: number;
  area?: boolean;
}) {
  const id = useId().replace(/:/g, "");
  if (data.length < 2) return null;
  const w = 120;
  const h = height;
  const min = Math.min(...data);
  const max = Math.max(...data);
  const span = max - min || 1;
  const pts = data.map((v, i) => [(i / (data.length - 1)) * w, h - 3 - ((v - min) / span) * (h - 8)] as const);
  const line = pts.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join("");
  const last = pts[pts.length - 1];
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" className={cn("h-9 w-full overflow-visible", className)} aria-hidden>
      <defs>
        <linearGradient id={`sg-${id}`} x1="0" x2="0" y1="0" y2="1">
          <stop offset="0%" stopColor={color} stopOpacity="0.28" />
          <stop offset="100%" stopColor={color} stopOpacity="0" />
        </linearGradient>
      </defs>
      {area ? <path d={`${line}L${w} ${h}L0 ${h}Z`} fill={`url(#sg-${id})`} /> : null}
      <path d={line} fill="none" stroke={color} strokeWidth="1.6" strokeLinejoin="round" strokeLinecap="round" vectorEffect="non-scaling-stroke" />
      <circle cx={last[0]} cy={last[1]} r="2.6" fill={color} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}
