"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { formatDay } from "@/lib/format";
import type { ExposureDay } from "@/lib/types";
import { cn } from "@/lib/utils";

export type HeatMetric = "pm25" | "db" | "rideMin";

const CELL = 12;
const GAP = 3;
const STEP = CELL + GAP;
const LEFT = 30;
const TOP = 18;
const WEEKDAYS = ["Mon", "", "Wed", "", "Fri", "", ""];

interface Level {
  id: string;
  label: string;
  color: string;
  opacity?: number;
}

/** Classes per metric: regulatory thresholds for air and noise, minutes for riding time. */
export const HEAT_LEVELS: Record<HeatMetric, { levels: Level[]; classify: (d: ExposureDay) => number }> = {
  pm25: {
    levels: [
      { id: "low", label: "≤ 10 µg/m³ · under the EU 2030 limit", color: "var(--good-fill)" },
      { id: "mid", label: "10–15 · under the WHO 24 h guideline", color: "var(--mid-fill)" },
      { id: "high", label: "> 15 · above the WHO 24 h guideline", color: "var(--bad-fill)" },
    ],
    classify: (d) => (d.pm25 === null ? -1 : d.pm25 <= 10 ? 0 : d.pm25 <= 15 ? 1 : 2),
  },
  db: {
    levels: [
      { id: "low", label: "≤ 58 dB(A) · quiet streets", color: "var(--good-fill)" },
      { id: "mid", label: "58–64 · busy", color: "var(--mid-fill)" },
      { id: "high", label: "> 64 · loud", color: "var(--bad-fill)" },
    ],
    classify: (d) => (d.db === null ? -1 : d.db <= 58 ? 0 : d.db <= 64 ? 1 : 2),
  },
  rideMin: {
    levels: [
      { id: "1", label: "< 25 min", color: "var(--color-signal)", opacity: 0.3 },
      { id: "2", label: "25–40 min", color: "var(--color-signal)", opacity: 0.55 },
      { id: "3", label: "40–55 min", color: "var(--color-signal)", opacity: 0.8 },
      { id: "4", label: "> 55 min", color: "var(--color-signal)", opacity: 1 },
    ],
    classify: (d) => (d.rideMin === 0 ? -1 : d.rideMin < 25 ? 0 : d.rideMin < 40 ? 1 : d.rideMin < 55 ? 2 : 3),
  },
};

function valueText(d: ExposureDay, metric: HeatMetric) {
  if (d.rideMin === 0) return "No ride";
  if (metric === "pm25") return `${d.pm25?.toFixed(1)} µg/m³ PM2.5 · ${d.rideMin} min`;
  if (metric === "db") return `${d.db?.toFixed(1)} dB(A) · ${d.rideMin} min`;
  return `${d.rideMin} min riding · ${d.pm25?.toFixed(1)} µg/m³`;
}

/**
 * GitHub-style year view: one square per day, Monday on top. The grid itself is
 * decorative for screen readers; the caption carries the same information.
 */
export function CalendarHeatmap({ days, metric, className }: { days: ExposureDay[]; metric: HeatMetric; className?: string }) {
  const [hover, setHover] = useState<{ i: number; x: number; y: number } | null>(null);
  const figRef = useRef<HTMLElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  // On narrow screens the year scrolls sideways: start on the most recent weeks.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollLeft = el.scrollWidth;
  }, []);
  const { cells, months, cols } = useMemo(() => {
    const first = new Date(`${days[0].date}T12:00:00Z`);
    const offset = (first.getUTCDay() + 6) % 7; // Monday = 0
    const out = days.map((d, i) => {
      const k = i + offset;
      return { d, col: Math.floor(k / 7), row: k % 7 };
    });
    const m: { col: number; label: string }[] = [];
    let last = "";
    for (const c of out) {
      const key = c.d.date.slice(0, 7);
      if (key !== last && c.row === 0) {
        last = key;
        m.push({ col: c.col, label: new Intl.DateTimeFormat("en-GB", { month: "short", timeZone: "UTC" }).format(new Date(`${c.d.date}T12:00:00Z`)) });
      }
    }
    return { cells: out, months: m.filter((x, i, a) => i === 0 || x.col - a[i - 1].col >= 3), cols: out[out.length - 1].col + 1 };
  }, [days]);

  const spec = HEAT_LEVELS[metric];
  const counts = spec.levels.map((_, li) => days.filter((d) => spec.classify(d) === li).length);
  const ridden = days.filter((d) => d.rideMin > 0).length;
  const width = LEFT + cols * STEP;
  const height = TOP + 7 * STEP;
  const h = hover ? cells[hover.i] : null;

  return (
    <figure ref={figRef} className={cn("relative", className)}>
      <figcaption className="sr-only">
        {ridden} riding days in the last 12 months.{" "}
        {spec.levels.map((l, i) => `${counts[i]} days ${l.label}`).join(", ")}.
      </figcaption>
      <div ref={scrollRef} className="scrollbar-none -mx-1 overflow-x-auto px-1 pb-1" onScroll={() => setHover(null)}>
        <svg viewBox={`0 0 ${width} ${height}`} className="block h-auto w-full max-w-[1040px]" style={{ minWidth: width }} aria-hidden onMouseLeave={() => setHover(null)}>
          {months.map((m) => (
            <text key={`${m.col}-${m.label}`} x={LEFT + m.col * STEP} y={11} className="fill-[var(--fg-subtle)] font-mono text-[10px]">
              {m.label}
            </text>
          ))}
          {WEEKDAYS.map((w, r) =>
            w ? (
              <text key={w} x={0} y={TOP + r * STEP + CELL - 2} className="fill-[var(--fg-subtle)] font-mono text-[10px]">
                {w}
              </text>
            ) : null,
          )}
          {cells.map((c, i) => {
            const li = spec.classify(c.d);
            const level = li >= 0 ? spec.levels[li] : null;
            const x = LEFT + c.col * STEP;
            const y = TOP + c.row * STEP;
            return (
              <rect
                key={c.d.date}
                x={x}
                y={y}
                width={CELL}
                height={CELL}
                rx={3}
                fill={level ? level.color : "var(--surface-3)"}
                fillOpacity={level ? (level.opacity ?? 0.92) : 0.7}
                stroke={hover?.i === i ? "var(--fg)" : "none"}
                strokeWidth={1.5}
                onMouseEnter={(e) => {
                  const r = e.currentTarget.getBoundingClientRect();
                  const f = figRef.current?.getBoundingClientRect();
                  setHover({ i, x: r.left + r.width / 2 - (f?.left ?? 0), y: r.top - (f?.top ?? 0) });
                }}
              />
            );
          })}
        </svg>
      </div>
      {h && hover ? (
        <div
          className="pointer-events-none absolute z-10 rounded-lg border border-line bg-surface px-2.5 py-1.5 text-xs whitespace-nowrap shadow-[var(--shadow-lift)]"
          style={{ left: hover.x, top: hover.y, transform: "translate(-50%, calc(-100% - 8px))" }}
          aria-hidden
        >
          <span className="font-medium text-fg">{formatDay(`${h.d.date}T12:00:00Z`, { weekday: "short", day: "numeric", month: "short" })}</span>
          <span className="text-fg-muted"> · {valueText(h.d, metric)}</span>
        </div>
      ) : null}
      <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-xs text-fg-muted" aria-hidden>
        <span className="inline-flex items-center gap-1.5">
          <span className="size-2.5 rounded-[3px] bg-surface-3" /> No ride
        </span>
        {spec.levels.map((l, i) => (
          <span key={l.id} className="inline-flex items-center gap-1.5">
            <span className="size-2.5 rounded-[3px]" style={{ background: l.color, opacity: l.opacity ?? 0.92 }} />
            {l.label} <span className="font-num text-fg-subtle">({counts[i]})</span>
          </span>
        ))}
      </div>
    </figure>
  );
}
