import type { Kpi } from "@/lib/types";
import { cn } from "@/lib/utils";
import { Delta } from "./delta";
import { Sparkline } from "./sparkline";

const fmt = (v: number) => (Math.abs(v) >= 1000 ? v.toLocaleString("en-US") : v.toLocaleString("en-US", { maximumFractionDigits: 1 }));

/** City Insights KPI: value, delta vs previous period, 12-week sparkline. */
export function KpiTile({ kpi, className }: { kpi: Kpi; className?: string }) {
  const overLimit = kpi.limit !== undefined && kpi.value > kpi.limit;
  return (
    <div className={cn("flex min-w-0 flex-col rounded-2xl border border-line bg-surface p-4", className)}>
      <div className="label-mono text-fg-subtle">{kpi.label}</div>
      <div className="mt-2 flex items-baseline gap-1.5">
        <span className="font-num text-[28px] leading-8 font-semibold text-fg">{fmt(kpi.value)}</span>
        {kpi.unit ? <span className="text-xs text-fg-muted">{kpi.unit}</span> : null}
      </div>
      <Delta value={kpi.delta} unit={kpi.deltaUnit === "%" ? "%" : kpi.deltaUnit ? ` ${kpi.deltaUnit}` : ""} better={kpi.better} className="mt-1" suffix={kpi.deltaLabel ?? "vs prev."} />
      {kpi.limit !== undefined ? (
        <div className="mt-3">
          <div className="flex justify-between text-[11px] text-fg-muted">
            <span>{kpi.limitLabel}</span>
            <span className="font-mono">{kpi.limit} {kpi.unit}</span>
          </div>
          <div className="relative mt-1 h-1.5 rounded-full bg-surface-3" aria-hidden>
            <div className="absolute inset-y-0 left-0 rounded-full" style={{ width: `${Math.min(100, (kpi.value / (kpi.limit * 2)) * 100)}%`, background: overLimit ? "var(--bad-fill)" : "var(--good-fill)" }} />
            <div className="absolute -top-1 h-3.5 w-0.5 rounded bg-fg" style={{ left: "50%" }} />
          </div>
          <p className="mt-1 text-[11px] text-fg-muted">{overLimit ? `${Math.round((kpi.value / kpi.limit - 1) * 100)}% above the limit` : "Within the limit"}</p>
        </div>
      ) : (
        <Sparkline data={kpi.spark} className="mt-auto pt-3" color={kpi.better === "up" ? (kpi.delta >= 0 ? "var(--good-fill)" : "var(--bad-fill)") : kpi.delta <= 0 ? "var(--good-fill)" : "var(--bad-fill)"} />
      )}
    </div>
  );
}
