import { cn } from "@/lib/utils";

export function Progress({ value, max = 100, className, barClassName, label }: { value: number; max?: number; className?: string; barClassName?: string; label: string }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div role="progressbar" aria-label={label} aria-valuemin={0} aria-valuemax={max} aria-valuenow={Math.round(value)} className={cn("h-2 w-full overflow-hidden rounded-full bg-surface-3", className)}>
      <div className={cn("h-full origin-left rounded-full bg-signal transition-transform duration-700 ease-[var(--ease-out-expo)]", barClassName)} style={{ transform: `scaleX(${pct / 100})` }} />
    </div>
  );
}
