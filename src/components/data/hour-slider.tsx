"use client";

import { Pause, Play } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Slider } from "@/components/ui/slider";
import { hourLabel } from "@/lib/format";
import { cn } from "@/lib/utils";

/** 0–23 h slider with a play button that animates through the day. */
export function HourSlider({ value, onChange, className, compact }: { value: number; onChange: (h: number) => void; className?: string; compact?: boolean }) {
  const [playing, setPlaying] = useState(false);
  const valueRef = useRef(value);
  valueRef.current = value;

  useEffect(() => {
    if (!playing) return;
    const id = window.setInterval(() => onChange((valueRef.current + 1) % 24), 650);
    return () => window.clearInterval(id);
  }, [playing, onChange]);

  return (
    <div className={cn("flex items-center gap-3", className)}>
      <button
        type="button"
        onClick={() => setPlaying((p) => !p)}
        aria-label={playing ? "Pause the day animation" : "Play through the day"}
        aria-pressed={playing}
        className="flex size-9 shrink-0 items-center justify-center rounded-full bg-signal text-asphalt-900 transition-transform hover:scale-105 active:scale-95"
      >
        {playing ? <Pause className="size-4" /> : <Play className="size-4 translate-x-px" />}
      </button>
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between">
          <span className="text-[11px] text-fg-muted">{compact ? "Hour" : "Time of day"}</span>
          <span className="font-num text-base font-semibold text-fg" aria-live="polite">
            {hourLabel(value)}
          </span>
        </div>
        <Slider
          value={[value]}
          min={0}
          max={23}
          step={1}
          thumbLabel="Hour of the day"
          onValueChange={([h]) => {
            setPlaying(false);
            onChange(h);
          }}
          className="mt-1"
        />
        {!compact ? (
          <div className="mt-1 flex justify-between font-mono text-[10px] text-fg-subtle" aria-hidden>
            <span>00</span>
            <span>06</span>
            <span>12</span>
            <span>18</span>
            <span>23</span>
          </div>
        ) : null}
      </div>
    </div>
  );
}
