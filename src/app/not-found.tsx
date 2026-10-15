import type { Metadata } from "next";
import Link from "next/link";
import { Logo } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = { title: "Page not found" };

/** 404: the trace runs off the grid. */
export default function NotFound() {
  return (
    <main className="grain relative flex min-h-dvh flex-col overflow-hidden bg-asphalt-900 text-paper">
      <svg aria-hidden className="pointer-events-none absolute inset-0 size-full opacity-60" viewBox="0 0 1200 800" preserveAspectRatio="xMidYMid slice">
        <g stroke="#26344f" strokeWidth="1" fill="none">
          {Array.from({ length: 22 }, (_, i) => (
            <path key={`a${i}`} d={`M${-400 + i * 90} 900 L${300 + i * 90} 0`} />
          ))}
          {Array.from({ length: 22 }, (_, i) => (
            <path key={`b${i}`} d={`M${-300 + i * 90} 0 L${400 + i * 90} 900`} />
          ))}
        </g>
        <path d="M170 690 L345 465 L455 553 L610 355 L700 427" fill="none" stroke="#ff5b1f" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M700 427 L760 476" fill="none" stroke="#ff5b1f" strokeWidth="5" strokeLinecap="round" strokeDasharray="2 14" />
        <circle cx="170" cy="690" r="9" fill="#0b1220" stroke="#f6f4ef" strokeWidth="4" />
        <circle cx="790" cy="500" r="26" fill="none" stroke="#ff5b1f" strokeOpacity="0.5" strokeWidth="2" strokeDasharray="4 6" />
      </svg>
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_at_center,transparent_10%,#0b1220_75%)]" />
      <header className="relative px-6 py-6 sm:px-10">
        <Link href="/" aria-label="UMI home" className="inline-block text-paper">
          <Logo className="h-6" />
        </Link>
      </header>
      <div className="relative flex flex-1 flex-col items-start justify-center px-6 pb-24 sm:px-10 lg:px-24">
        <p className="label-mono text-signal">Error 404 · signal lost</p>
        <h1 className="mt-4 max-w-2xl font-display text-5xl leading-[1.02] font-semibold tracking-tight text-balance sm:text-7xl">This street isn&apos;t on the map yet.</h1>
        <p className="mt-5 max-w-lg text-lg text-asphalt-200">The page you&apos;re looking for doesn&apos;t exist, or it moved. The streets you ride are still here.</p>
        <div className="mt-9 flex flex-wrap gap-3">
          <Button asChild size="lg" pill>
            <Link href="/">Back to umi.city</Link>
          </Button>
          <Button asChild size="lg" pill variant="glass">
            <Link href="/app/map">Open the street map</Link>
          </Button>
        </div>
      </div>
    </main>
  );
}
