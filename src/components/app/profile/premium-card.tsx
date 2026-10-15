"use client";

import { Check, Sparkles } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Segmented } from "@/components/ui/segmented";
import { formatDay } from "@/lib/format";
import { mockNow } from "@/lib/mock";
import { cn } from "@/lib/utils";

const FEATURES = [
  { title: "Calmest & Cleanest routes", body: "Every trip planned around the streets that feel best at your departure time." },
  { title: "Your full exposure history", body: "Every ride since day one, monthly reports and a yearly PDF for your doctor." },
  { title: "Street alerts", body: "A heads-up when air or traffic on your usual streets is worse than normal." },
  { title: "Priority firmware", body: "New Clip features first, like the upcoming crash detection." },
];

const PRICES = {
  monthly: { price: "€4.99", per: "per month", note: "Billed monthly · cancel anytime" },
  yearly: { price: "€39.99", per: "per year", note: "€3.33 a month · save 33%" },
} as const;

/** The upsell: calm, honest, one clear action. */
export function PremiumCard() {
  const [plan, setPlan] = useState<"monthly" | "yearly">("yearly");
  const [started, setStarted] = useState(false);
  const p = PRICES[plan];
  return (
    <section id="premium" aria-labelledby="premium-title" className="relative scroll-mt-24 overflow-hidden rounded-3xl border border-line bg-asphalt-900 text-paper shadow-[var(--shadow-lift)]">
      <div aria-hidden className="grain pointer-events-none absolute inset-0 opacity-60" />
      <div aria-hidden className="absolute -top-32 -right-24 size-80 rounded-full bg-signal/25 blur-3xl" />
      <div aria-hidden className="absolute -bottom-40 left-1/4 size-80 rounded-full bg-lane/15 blur-3xl" />
      <div className="relative grid grid-cols-1 gap-8 p-6 sm:p-8 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div>
          <p className="label-mono flex items-center gap-2 text-signal">
            <Sparkles className="size-3.5" /> UMI Premium
          </p>
          <h2 id="premium-title" className="mt-3 font-display text-3xl leading-tight font-semibold tracking-tight text-balance sm:text-[34px]">
            Ride the calm side of Barcelona.
          </h2>
          <p className="mt-3 max-w-lg text-[15px] leading-7 text-asphalt-200">
            The Clip and the street map stay free, for everyone. Premium is for riders who want UMI to plan around their lungs and their nerves, every day.
          </p>
          <ul className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2">
            {FEATURES.map((f) => (
              <li key={f.title} className="flex gap-3">
                <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-signal/20 text-signal" aria-hidden>
                  <Check className="size-3" strokeWidth={3} />
                </span>
                <span>
                  <span className="block text-sm font-semibold text-paper">{f.title}</span>
                  <span className="block text-[13px] leading-5 text-asphalt-300">{f.body}</span>
                </span>
              </li>
            ))}
          </ul>
        </div>

        <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-5 backdrop-blur-sm">
          <div className="dark">
            <Segmented
              value={plan}
              onChange={setPlan}
              label="Billing period"
              className="w-full [&>button]:flex-1"
              options={[
                { value: "monthly", label: "Monthly" },
                { value: "yearly", label: "Yearly −33%" },
              ]}
            />
          </div>
          <p className="mt-5 flex items-baseline gap-2">
            <span className="font-num text-5xl font-semibold tracking-tight text-paper">{p.price}</span>
            <span className="text-sm text-asphalt-300">{p.per}</span>
          </p>
          <p className="mt-1 text-xs text-asphalt-300">{p.note}</p>
          <Button size="lg" pill className={cn("mt-5 w-full", started && "pointer-events-none")} onClick={() => setStarted(true)} aria-live="polite">
            {started ? (
              <>
                <Check /> Trial started
              </>
            ) : (
              "Start your 30-day free trial"
            )}
          </Button>
          <p className="mt-3 text-center text-[11px] leading-4 text-asphalt-400">
            No charge until {formatDay(new Date(mockNow().getTime() + 30 * 86_400_000).toISOString(), { day: "numeric", month: "long" })}. Your data stays yours, on any plan.
          </p>
        </div>
      </div>
    </section>
  );
}
