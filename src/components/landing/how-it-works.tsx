"use client";

import { Bike, BarChart3, Paperclip, RefreshCcw, Route } from "lucide-react";
import { useRef } from "react";
import { gsap, useGSAP } from "./motion";

const STEPS = [
  { icon: Paperclip, title: "Clip on", body: "Bike, scooter, bag strap or running belt. Tool-free mount, ten seconds." },
  { icon: Bike, title: "Ride or run", body: "UMI measures quietly. No phone needed on the way, no button to press." },
  { icon: RefreshCcw, title: "Auto-sync", body: "Bluetooth sync when you're home or at work. Sound is reduced to dB on the Clip." },
  { icon: BarChart3, title: "Ride report", body: "Comfort, safety, air and noise, with the moments that mattered." },
  { icon: Route, title: "Better route", body: "Tomorrow's ride, tuned to what you care about: fastest, calmest or cleanest." },
];

export function HowItWorks() {
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add({ desktop: "(min-width: 1024px) and (prefers-reduced-motion: no-preference)", mobile: "(max-width: 1023px) and (prefers-reduced-motion: no-preference)" }, (ctx) => {
        const { desktop } = ctx.conditions as Record<string, boolean>;
        const steps = gsap.utils.toArray<HTMLElement>(".hiw-step");
        const tl = gsap.timeline({
          scrollTrigger: { trigger: ".hiw-list", start: desktop ? "top 70%" : "top 75%", end: desktop ? "bottom 55%" : "bottom 60%", scrub: 0.6 },
        });
        tl.fromTo(".hiw-line", desktop ? { scaleX: 0 } : { scaleY: 0 }, desktop ? { scaleX: 1, ease: "none", duration: 1 } : { scaleY: 1, ease: "none", duration: 1 }, 0);
        steps.forEach((step, i) => {
          const at = i / (steps.length - 1);
          tl.fromTo(step.querySelector(".hiw-node"), { scale: 0.7, opacity: 0.35 }, { scale: 1, opacity: 1, duration: 0.12, ease: "back.out(2)" }, Math.max(0, at - 0.06))
            .fromTo(step.querySelector(".hiw-fill"), { opacity: 0 }, { opacity: 1, duration: 0.1 }, Math.max(0, at - 0.04))
            .fromTo(step.querySelector(".hiw-copy"), { opacity: 0.3, y: 10 }, { opacity: 1, y: 0, duration: 0.14 }, Math.max(0, at - 0.06));
        });
      });
    },
    { scope: root },
  );

  return (
    <section ref={root} id="how-it-works" aria-labelledby="hiw-title" className="relative bg-asphalt-900 py-28 sm:py-36">
      <div className="mx-auto max-w-6xl px-5 sm:px-8">
        <p className="label-mono text-signal">How it works</p>
        <h2 id="hiw-title" className="mt-3 max-w-2xl font-display text-4xl font-semibold tracking-tight text-paper sm:text-5xl">
          From your morning ride to a better map.
        </h2>
        <div className="hiw-list relative mt-16">
          <div aria-hidden className="absolute top-0 bottom-0 left-[27px] w-[2px] bg-white/8 lg:top-[27px] lg:right-[10%] lg:bottom-auto lg:left-[10%] lg:h-[2px] lg:w-auto">
            <div className="hiw-line size-full origin-top bg-signal lg:origin-left" />
          </div>
          <ol className="relative grid gap-10 lg:grid-cols-5 lg:gap-6">
          {STEPS.map((s, i) => (
            <li key={s.title} className="hiw-step relative flex gap-5 lg:flex-col lg:items-center lg:gap-6 lg:text-center">
              <div className="hiw-node relative z-10 flex size-14 shrink-0 items-center justify-center rounded-2xl border border-white/10 bg-asphalt-850">
                <div className="hiw-fill absolute inset-0 rounded-2xl bg-signal opacity-0" />
                <s.icon className="relative size-6 text-paper" />
              </div>
              <div className="hiw-copy">
                <p className="font-mono text-xs text-asphalt-400">0{i + 1}</p>
                <h3 className="mt-1 font-display text-xl font-semibold text-paper">{s.title}</h3>
                <p className="mt-2 text-sm leading-6 text-asphalt-300 lg:mx-auto lg:max-w-[13rem]">{s.body}</p>
              </div>
            </li>
          ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
