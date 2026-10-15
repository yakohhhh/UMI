import { AlertTriangle, MapPinOff, RefreshCw } from "lucide-react";
import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function EmptyState({ title, body, icon, action, className }: { title: string; body?: ReactNode; icon?: ReactNode; action?: ReactNode; className?: string }) {
  return (
    <div className={cn("flex flex-col items-center justify-center rounded-2xl border border-dashed border-line-strong px-6 py-12 text-center", className)}>
      <div className="flex size-11 items-center justify-center rounded-2xl bg-surface-2 text-fg-muted [&_svg]:size-5">{icon ?? <MapPinOff />}</div>
      <h3 className="mt-4 font-display text-base font-semibold text-fg">{title}</h3>
      {body ? <p className="mt-1.5 max-w-sm text-sm text-fg-muted">{body}</p> : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

export function ErrorState({ error, onRetry, className, compact }: { error?: Error; onRetry?: () => void; className?: string; compact?: boolean }) {
  return (
    <div
      role="alert"
      className={cn(
        "flex flex-col items-center justify-center rounded-2xl border border-bad/30 bg-bad/[0.06] px-6 text-center",
        compact ? "py-6" : "py-12",
        className,
      )}
    >
      <div className="flex size-11 items-center justify-center rounded-2xl bg-bad/15 text-bad">
        <AlertTriangle className="size-5" />
      </div>
      <h3 className="mt-4 font-display text-base font-semibold text-fg">We couldn't load this data</h3>
      <p className="mt-1.5 max-w-sm text-sm text-fg-muted">{error?.message ?? "Something went wrong on our side."} Your rides are safe on the Clip and will sync again.</p>
      {onRetry ? (
        <Button variant="secondary" size="sm" className="mt-5" onClick={onRetry}>
          <RefreshCw /> Try again
        </Button>
      ) : null}
    </div>
  );
}
