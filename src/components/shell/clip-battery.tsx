import { cn } from "@/lib/utils";

/** Battery glyph with fill level + percentage. */
export function ClipBattery({ level, className, showLabel = true }: { level: number; className?: string; showLabel?: boolean }) {
  const low = level <= 20;
  return (
    <span className={cn("inline-flex items-center gap-1.5", className)}>
      <span aria-hidden className="relative inline-flex h-[11px] w-[22px] items-center rounded-[3px] border border-fg-subtle p-[1.5px]">
        <span className={cn("h-full rounded-[1.5px]", low ? "bg-bad-fill" : "bg-fg")} style={{ width: `${Math.max(8, level)}%` }} />
        <span className="absolute top-1/2 -right-[3px] h-[5px] w-[2px] -translate-y-1/2 rounded-r-sm bg-fg-subtle" />
      </span>
      {showLabel ? <span className="font-mono text-[11px] text-fg">{level}%</span> : null}
    </span>
  );
}
