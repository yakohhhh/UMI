import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

/** Big number with a mono label — the Strava-style weekly stats block. */
export function StatTile({
  label,
  value,
  unit,
  sub,
  icon,
  className,
  size = "md",
}: {
  label: string;
  value: ReactNode;
  unit?: string;
  sub?: ReactNode;
  icon?: ReactNode;
  className?: string;
  size?: "sm" | "md" | "lg";
}) {
  return (
    <div className={cn("min-w-0", className)}>
      <div className="flex items-center gap-1.5 label-mono text-fg-subtle [&_svg]:size-3.5">
        {icon}
        {label}
      </div>
      <div className="mt-1.5 flex items-baseline gap-1">
        <span className={cn("font-num font-semibold text-fg", size === "lg" ? "text-4xl" : size === "md" ? "text-[26px] leading-8" : "text-xl")}>{value}</span>
        {unit ? <span className="text-sm text-fg-muted">{unit}</span> : null}
      </div>
      {sub ? <div className="mt-1 text-xs text-fg-muted">{sub}</div> : null}
    </div>
  );
}
