"use client";

import { Check } from "lucide-react";
import Link from "next/link";
import { useRef, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/segmented";
import { cn } from "@/lib/utils";

/** Card that tilts toward the pointer with a soft glow following it (transform + opacity only). */
function TiltCard({ children, className, highlight }: { children: ReactNode; className?: string; highlight?: boolean }) {
  const ref = useRef<HTMLDivElement>(null);
  const glowRef = useRef<HTMLDivElement>(null);
  const frame = useRef(0);

  const onMove = (e: React.PointerEvent) => {
    if (e.pointerType !== "mouse" || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const el = ref.current!;
    const r = el.getBoundingClientRect();
    const x = (e.clientX - r.left) / r.width;
    const y = (e.clientY - r.top) / r.height;
    cancelAnimationFrame(frame.current);
    frame.current = requestAnimationFrame(() => {
      el.style.transform = `perspective(1000px) rotateX(${(0.5 - y) * 7}deg) rotateY(${(x - 0.5) * 9}deg) translateZ(0)`;
      if (glowRef.current) {
        glowRef.current.style.opacity = "1";
        glowRef.current.style.transform = `translate(${x * r.width - 200}px, ${y * r.height - 200}px)`;
      }
    });
  };
  const onLeave = () => {
    cancelAnimationFrame(frame.current);
    if (ref.current) ref.current.style.transform = "";
    if (glowRef.current) glowRef.current.style.opacity = "0";
  };

  return (
    <div
      ref={ref}
      onPointerMove={onMove}
      onPointerLeave={onLeave}
      className={cn(
        "group relative flex flex-col overflow-hidden rounded-[28px] border bg-asphalt-850 p-7 transition-transform duration-500 ease-out-expo will-change-transform sm:p-8",
        highlight ? "border-signal/40" : "border-white/10",
        className,
      )}
    >
      <div
        ref={glowRef}
        aria-hidden
        className="pointer-events-none absolute top-0 left-0 size-[400px] rounded-full opacity-0 transition-opacity duration-300"
        style={{ background: `radial-gradient(circle, ${highlight ? "rgb(255 91 31 / 0.22)" : "rgb(47 127 255 / 0.16)"}, transparent 65%)` }}
      />
      <div className="relative flex flex-1 flex-col">{children}</div>
    </div>
  );
}

function Features({ items }: { items: string[] }) {
  return (
    <ul className="mt-6 space-y-3 text-sm text-asphalt-200">
      {items.map((f) => (
        <li key={f} className="flex gap-2.5">
          <Check className="mt-0.5 size-4 shrink-0 text-signal" aria-hidden />
          {f}
        </li>
      ))}
    </ul>
  );
}

export function Pricing() {
  const [billing, setBilling] = useState<"monthly" | "yearly">("yearly");

  return (
    <section id="pricing" aria-labelledby="pricing-title" className="relative bg-asphalt-950 py-28 sm:py-36">
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <div className="max-w-2xl">
          <p className="label-mono text-signal">Pricing</p>
          <h2 id="pricing-title" className="mt-3 font-display text-4xl font-semibold tracking-tight text-paper sm:text-5xl">
            One clip. A free app. Data cities can use.
          </h2>
        </div>

        <div className="mt-14 grid gap-5 lg:grid-cols-3">
          <TiltCard highlight>
            <div className="flex items-center justify-between">
              <h3 className="font-display text-xl font-semibold text-paper">UMI Clip</h3>
              <span className="rounded-full bg-signal px-2.5 py-1 text-[11px] font-semibold text-asphalt-900">Early bird</span>
            </div>
            <p className="mt-6 flex items-baseline gap-3">
              <span className="font-num text-5xl font-semibold text-paper">€99</span>
              <span className="text-lg text-asphalt-400 line-through" aria-label="instead of €119">
                €119
              </span>
            </p>
            <p className="mt-1 text-sm text-asphalt-300">One-time · first 600 riders · then €119</p>
            <Features items={["Comfort, safety, air and noise sensors", "A week of commutes per charge, USB-C", "Clips on bike, scooter, bag strap or belt", "Free UMI app with every ride report"]} />
            <div className="mt-auto pt-8">
              <Button asChild size="lg" pill className="w-full">
                <a href="#preorder">Pre-order — €99</a>
              </Button>
            </div>
          </TiltCard>

          <TiltCard>
            <div className="flex items-center justify-between gap-3">
              <h3 className="font-display text-xl font-semibold text-paper">UMI Premium</h3>
              <Segmented
                value={billing}
                onChange={setBilling}
                size="sm"
                label="Billing period"
                className="border-white/10 bg-white/5"
                options={[
                  { value: "monthly", label: "Monthly" },
                  { value: "yearly", label: "Yearly" },
                ]}
              />
            </div>
            <p className="mt-6 flex items-baseline gap-2">
              <span className="font-num text-5xl font-semibold text-paper">{billing === "yearly" ? "€39.99" : "€4.99"}</span>
              <span className="text-asphalt-400">/{billing === "yearly" ? "year" : "month"}</span>
            </p>
            <p className="mt-1 text-sm text-asphalt-300">{billing === "yearly" ? "€3.33 a month · save 33%" : "Cancel anytime"}</p>
            <Features items={["Calmest and cleanest route planner", "Hour-by-hour street map", "Exposure history vs WHO and EU limits", "Export all your data, anytime"]} />
            <p className="mt-6 text-xs text-asphalt-400">The app stays free: ride reports, street map, weekly stats.</p>
            <div className="mt-auto pt-6">
              <Button variant="glass" size="lg" pill className="w-full">
                Start a 30-day trial
              </Button>
            </div>
          </TiltCard>

          <TiltCard>
            <h3 className="font-display text-xl font-semibold text-paper">City Insights</h3>
            <p className="mt-6 flex items-baseline gap-2">
              <span className="font-num text-5xl font-semibold text-paper">€14,900</span>
            </p>
            <p className="mt-1 text-sm text-asphalt-300">3-month pilot · then annual licence</p>
            <Features items={["Surface index and repair priorities", "Hard-brake hotspots by junction", "Hourly air and noise exposure", "API and CSV exports, GDPR by design"]} />
            <p className="mt-6 text-xs text-asphalt-400">For city councils, bike-share operators and fleets.</p>
            <div className="mt-auto pt-6">
              <Button asChild variant="paper" size="lg" pill className="w-full">
                <Link href="/city">See the dashboard</Link>
              </Button>
            </div>
          </TiltCard>
        </div>
      </div>
    </section>
  );
}
