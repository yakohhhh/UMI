"use client";

import * as ToggleGroup from "@radix-ui/react-toggle-group";
import * as React from "react";
import { cn } from "@/lib/utils";

export interface SegmentedOption<T extends string> {
  value: T;
  label: React.ReactNode;
  icon?: React.ReactNode;
}

/**
 * Single-choice segmented control (Radix ToggleGroup) with a sliding thumb.
 * Keyboard: arrows move, Space/Enter selects. The thumb is a CSS transition
 * (no animation library), so the landing's pricing toggle stays light.
 */
export function Segmented<T extends string>({
  value,
  onChange,
  options,
  label,
  size = "md",
  className,
  id,
}: {
  value: T;
  onChange: (v: T) => void;
  options: SegmentedOption<T>[];
  label: string;
  size?: "sm" | "md";
  className?: string;
  id?: string;
}) {
  const rootRef = React.useRef<HTMLDivElement>(null);
  const [thumb, setThumb] = React.useState<{ x: number; w: number } | null>(null);
  React.useLayoutEffect(() => {
    const root = rootRef.current;
    if (!root) return;
    const measure = () => {
      const on = root.querySelector<HTMLElement>('[data-state="on"]');
      setThumb(on ? { x: on.offsetLeft, w: on.offsetWidth } : null);
    };
    measure();
    // labels can change width when fonts load or the container resizes
    const ro = new ResizeObserver(measure);
    ro.observe(root);
    return () => ro.disconnect();
  }, [value, options.length]);

  return (
    <ToggleGroup.Root
      ref={rootRef}
      type="single"
      value={value}
      onValueChange={(v) => v && onChange(v as T)}
      aria-label={label}
      id={id}
      className={cn("relative inline-flex items-center gap-0.5 rounded-xl border border-line bg-surface-2 p-0.5", className)}
    >
      {thumb ? (
        <span
          aria-hidden
          className="absolute top-0.5 bottom-0.5 left-0 rounded-[10px] border border-line-strong bg-surface shadow-[var(--shadow-soft)] transition-[transform,width] duration-300 ease-out-expo motion-reduce:transition-none"
          style={{ width: thumb.w, transform: `translateX(${thumb.x}px)` }}
        />
      ) : null}
      {options.map((o) => {
        const active = o.value === value;
        return (
          <ToggleGroup.Item
            key={o.value}
            value={o.value}
            className={cn(
              "relative inline-flex items-center justify-center gap-1.5 rounded-[10px] font-medium whitespace-nowrap transition-colors",
              size === "sm" ? "h-7 px-2.5 text-xs" : "h-8 px-3 text-[13px]",
              active ? "text-fg" : "text-fg-muted hover:text-fg",
            )}
          >
            <span className="relative z-10 inline-flex items-center gap-1.5 [&_svg]:size-3.5">
              {o.icon}
              {o.label}
            </span>
          </ToggleGroup.Item>
        );
      })}
    </ToggleGroup.Root>
  );
}
