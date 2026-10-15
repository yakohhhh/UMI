import type { ReactNode } from "react";

export function PageHeader({ eyebrow, title, description, children }: { eyebrow: string; title: string; description?: string; children?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-3">
      <div className="min-w-0">
        <p className="label-mono text-accent-ink">{eyebrow}</p>
        <h1 className="mt-1 font-display text-2xl font-semibold tracking-tight text-balance sm:text-[28px]">{title}</h1>
        {description ? <p className="mt-1.5 max-w-2xl text-sm text-fg-muted">{description}</p> : null}
      </div>
      {children}
    </header>
  );
}
