import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { cn } from "@/lib/utils";

/** Change vs the previous period. Blue = improvement, orange = worse (score scale). */
export function Delta({ value, unit = "", better = "up", className, suffix = "vs prev." }: { value: number; unit?: string; better?: "up" | "down"; className?: string; suffix?: string }) {
  const good = value === 0 ? null : better === "up" ? value > 0 : value < 0;
  const Icon = value === 0 ? Minus : value > 0 ? ArrowUpRight : ArrowDownRight;
  const text = `${value > 0 ? "+" : value < 0 ? "−" : "±"}${Math.abs(value).toLocaleString("en-US", { maximumFractionDigits: 1 })}${unit}`;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 text-xs font-medium tabular-nums",
        good === null ? "text-fg-muted" : good ? "text-good" : "text-bad",
        className,
      )}
      aria-label={`${text} ${suffix}, ${good === null ? "no change" : good ? "improving" : "worsening"}`}
    >
      <Icon className="size-3.5" aria-hidden />
      {text}
      {suffix ? <span className="ml-1 font-normal text-fg-subtle">{suffix}</span> : null}
    </span>
  );
}
