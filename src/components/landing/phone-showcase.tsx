"use client";

import { useRef, useState, type ReactNode } from "react";
import { BAND_COLORS, scoreBand } from "@/lib/score";
import { cn } from "@/lib/utils";
import { phoneMap } from "./data/geo";
import { gsap, ScrollTrigger, useGSAP } from "./motion";
import { RideReportScreen, RoutesScreen, StreetMapScreen } from "./phone-screens";

const STEPS = [
  {
    eyebrow: "Ride report",
    title: "Every ride, scored.",
    body: "Comfort, safety, air and noise for each ride, with the exact spots that made the difference — the junction where you braked, the pothole, the bus at Glòries.",
  },
  {
    eyebrow: "Street map",
    title: "Streets change by the hour.",
    body: "Slide through the day. The same bike lane can be calm at 3 pm and polluted at 8 am — the map shows what thousands of rides measured, hour by hour.",
  },
  {
    eyebrow: "Choose a route",
    title: "Pick the ride you want.",
    body: "Fastest, calmest or cleanest. UMI shows the trade-off and lets you choose: three extra minutes for a far calmer ride.",
  },
];

export function PhoneFrame({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={cn("relative h-[620px] w-[300px] rounded-[54px] bg-gradient-to-b from-[#3a4356] via-[#1b2130] to-[#3a4356] p-[3px] shadow-[0_60px_120px_-40px_rgb(0_0_0/0.95)]", className)}>
      <div className="relative size-full rounded-[51px] bg-[#05080e] p-[9px]">
        <div className="relative size-full overflow-hidden rounded-[43px] bg-asphalt-900">
          {children}
          <div aria-hidden className="absolute top-2.5 left-1/2 z-20 h-[26px] w-[92px] -translate-x-1/2 rounded-full bg-black" />
        </div>
      </div>
      <span aria-hidden className="absolute top-28 -left-[3px] h-14 w-[3px] rounded-l bg-[#2a3142]" />
      <span aria-hidden className="absolute top-32 -right-[3px] h-20 w-[3px] rounded-r bg-[#2a3142]" />
    </div>
  );
}

export function PhoneShowcase() {
  const root = useRef<HTMLElement>(null);
  const mapRef = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState(0);
  const hourRef = useRef(8);

  const paintHour = (h: number) => {
    const hour = Math.max(0, Math.min(23, Math.round(h)));
    if (hour === hourRef.current) return;
    hourRef.current = hour;
    const el = mapRef.current;
    if (!el) return;
    el.querySelectorAll<SVGPathElement>("[data-street]").forEach((p) => {
      const s = phoneMap.streets[Number(p.dataset.street)];
      p.setAttribute("stroke", BAND_COLORS.dark[scoreBand(s.overall[hour])]);
    });
    const label = el.querySelector(".phone-hour");
    if (label) label.textContent = `${String(hour).padStart(2, "0")}:00`;
    const fill = el.querySelector<HTMLElement>(".phone-hour-fill");
    if (fill) fill.style.transform = `scaleX(${hour / 23})`;
    const thumb = el.querySelector<HTMLElement>(".phone-hour-thumb");
    if (thumb) thumb.style.transform = `translate(calc(${(hour / 23) * 236}px - 50%), -50%)`;
  };

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(min-width: 1024px) and (prefers-reduced-motion: no-preference)", () => {
        const screens = gsap.utils.toArray<HTMLElement>(".ph-screen");
        const texts = gsap.utils.toArray<HTMLElement>(".ph-text");
        const dots = gsap.utils.toArray<HTMLElement>(".ph-dot");
        gsap.set(screens.slice(1), { yPercent: 12, opacity: 0, scale: 0.96 });
        gsap.set(texts.slice(1), { y: 40, opacity: 0 });
        const hour = { h: 8 };
        paintHour(8);
        const tl = gsap.timeline({
          defaults: { ease: "power3.inOut", duration: 0.5 },
          scrollTrigger: { trigger: root.current, start: "top top", end: "+=260%", pin: true, scrub: 0.8, anticipatePin: 1 },
        });
        const swap = (from: number, to: number, at: number) => {
          tl.to(screens[from], { yPercent: -8, opacity: 0, scale: 0.96 }, at)
            .to(screens[to], { yPercent: 0, opacity: 1, scale: 1 }, at)
            .to(texts[from], { y: -40, opacity: 0 }, at)
            .to(texts[to], { y: 0, opacity: 1 }, at + 0.1)
            .to(dots[to], { scaleX: 1, ease: "none", duration: 0.2 }, at);
        };
        tl.to(dots[0], { scaleX: 1, ease: "none", duration: 0.2 }, 0).to({}, { duration: 0.6 });
        swap(0, 1, 0.8);
        tl.to(hour, { h: 18, ease: "none", duration: 1.4, onUpdate: () => paintHour(hour.h) }, 1.4);
        swap(1, 2, 3.0);
        tl.fromTo(".route-calm", { scale: 1 }, { scale: 1.03, duration: 0.25, yoyo: true, repeat: 1 }, 3.5).fromTo(
          ".go-calm",
          { scale: 1, boxShadow: "0 0 0 0 rgba(255,91,31,0)" },
          { scale: 0.95, boxShadow: "0 0 0 10px rgba(255,91,31,0.25)", duration: 0.25, yoyo: true, repeat: 1 },
          3.9,
        );
        tl.to({}, { duration: 0.4 });
      });
      // Phones, and desktops with reduced motion: the steps scroll past a sticky phone.
      mm.add({ narrow: "(max-width: 1023px)", reduce: "(prefers-reduced-motion: reduce)" }, (ctx) => {
        const { narrow, reduce } = ctx.conditions as { narrow: boolean; reduce: boolean };
        if (!narrow && !reduce) return;
        const steps = gsap.utils.toArray<HTMLElement>(".ph-step").filter((step) => step.offsetParent !== null);
        steps.forEach((step, i) => {
          // Contiguous ranges (each step lasts until the next one starts), so a
          // keyboard page-jump can't skip a screen.
          ScrollTrigger.create({
            trigger: step,
            start: "top 60%",
            endTrigger: steps[i + 1] ?? step,
            end: steps[i + 1] ? "top 60%" : "bottom top",
            onToggle: (self) => {
              if (!self.isActive) return;
              setActive(i);
              if (i !== 1) return;
              if (reduce) {
                paintHour(18);
                return;
              }
              const hour = { h: 8 };
              gsap.to(hour, { h: 18, duration: 2.6, ease: "power1.inOut", onUpdate: () => paintHour(hour.h) });
            },
          });
        });
      });
    },
    { scope: root },
  );

  const screens = [<RideReportScreen key="r" />, <StreetMapScreen key="m" ref={mapRef} hour={8} />, <RoutesScreen key="t" />];

  return (
    <section ref={root} aria-labelledby="phone-title" className="relative bg-asphalt-900 lg:motion-safe:h-[100svh] lg:motion-safe:overflow-hidden">
      <div aria-hidden className="absolute inset-0 bg-[radial-gradient(circle_at_68%_50%,rgb(255_91_31/0.12),transparent_45%)]" />
      <div className="relative mx-auto grid max-w-6xl gap-10 px-5 py-24 sm:px-8 lg:grid-cols-2 lg:motion-safe:h-full lg:motion-safe:items-center lg:motion-safe:py-0">
        <div className="relative">
          <p className="label-mono text-signal">The UMI app</p>
          <h2 id="phone-title" className="sr-only">
            The UMI app: ride reports, street map and route choice
          </h2>
          {/* desktop: stacked, cross-fading copy */}
          <div className="relative mt-4 hidden h-[260px] lg:motion-safe:block">
            {STEPS.map((s, i) => (
              <div key={s.title} className="ph-text absolute inset-x-0 top-0">
                <p className="font-mono text-xs text-asphalt-400">
                  0{i + 1} · {s.eyebrow}
                </p>
                <h3 className="mt-3 font-display text-5xl leading-tight font-semibold tracking-tight text-balance text-paper">{s.title}</h3>
                <p className="mt-4 max-w-md text-lg leading-8 text-asphalt-200">{s.body}</p>
              </div>
            ))}
          </div>
          <div className="mt-6 hidden gap-2 lg:motion-safe:flex" aria-hidden>
            {STEPS.map((s) => (
              <span key={s.title} className="h-1 w-14 overflow-hidden rounded-full bg-white/10">
                <span className="ph-dot block h-full origin-left scale-x-0 bg-signal" />
              </span>
            ))}
          </div>
          {/* desktop with reduced motion: plain list, the phone follows */}
          <ol className="mt-6 hidden space-y-[40vh] pb-[30vh] lg:motion-reduce:block">
            {STEPS.map((s, i) => (
              <li key={s.title} className="ph-step">
                <p className="font-mono text-xs text-asphalt-400">
                  0{i + 1} · {s.eyebrow}
                </p>
                <h3 className="mt-3 font-display text-4xl leading-tight font-semibold tracking-tight text-balance text-paper">{s.title}</h3>
                <p className="mt-4 max-w-md text-lg leading-8 text-asphalt-200">{s.body}</p>
              </li>
            ))}
          </ol>
        </div>

        <div className="relative lg:flex lg:justify-center lg:motion-reduce:items-start">
          <div className="sticky top-20 z-10 flex justify-center lg:motion-safe:static lg:motion-reduce:top-[calc(50vh-310px)]">
            <PhoneFrame className="scale-[0.86] sm:scale-100">
              {screens.map((screen, i) => (
                <div
                  key={i}
                  className={cn(
                    "ph-screen absolute inset-0 transition-[opacity,transform] duration-700 ease-out-expo lg:transition-none",
                    active === i ? "opacity-100" : "pointer-events-none translate-y-6 opacity-0 lg:translate-y-0",
                  )}
                  aria-hidden={active !== i}
                >
                  {screen}
                </div>
              ))}
            </PhoneFrame>
          </div>
          {/* mobile: steps scroll past the sticky phone */}
          <ol className="relative z-20 mt-6 space-y-[45vh] pb-[20vh] lg:hidden">
            {STEPS.map((s, i) => (
              <li key={s.title} className="ph-step rounded-3xl border border-white/10 bg-asphalt-850/95 p-6 backdrop-blur-md">
                <p className="font-mono text-xs text-asphalt-400">
                  0{i + 1} · {s.eyebrow}
                </p>
                <h3 className="mt-2 font-display text-2xl font-semibold text-paper">{s.title}</h3>
                <p className="mt-2 text-asphalt-200">{s.body}</p>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
