import { cn } from "@/lib/utils";

/**
 * "umi" wordmark: lowercase letters drawn like a route, the tittle of the i is
 * the orange dot — the rider on the map.
 */
export function Logo({ className, pulse = false, title = "UMI" }: { className?: string; pulse?: boolean; title?: string }) {
  return (
    <svg viewBox="0 0 50 24" className={cn("h-6 w-auto", className)} role="img" aria-label={title}>
      <g fill="none" stroke="currentColor" strokeWidth="3.4" strokeLinecap="round" strokeLinejoin="round">
        <path d="M3.5 8.5v6a5 5 0 0 0 10 0v-6M13.5 14.5V20" />
        <path d="M20 20V8.5M20 13.4a4.6 4.6 0 0 1 9.2 0V20M29.2 13.4a4.6 4.6 0 0 1 9.2 0V20" />
        <path d="M45.4 11.2V20" />
      </g>
      {pulse ? <circle cx="45.4" cy="4.2" r="2.7" className="origin-[45.4px_4.2px] animate-pulse-dot fill-signal" /> : null}
      <circle cx="45.4" cy="4.2" r="2.7" className="fill-signal" />
    </svg>
  );
}

/** App icon / favicon mark: the dot on an asphalt tile. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <span className={cn("inline-flex size-8 items-center justify-center rounded-[10px] bg-asphalt-900 ring-1 ring-white/10", className)}>
      <svg viewBox="0 0 24 24" className="size-5" aria-hidden="true">
        <path d="M6 7v5.5a4.5 4.5 0 0 0 9 0V7" fill="none" stroke="#f6f4ef" strokeWidth="2.6" strokeLinecap="round" />
        <circle cx="18.8" cy="17.4" r="2.6" fill="#ff5b1f" />
      </svg>
    </span>
  );
}
