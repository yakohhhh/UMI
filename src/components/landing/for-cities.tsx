"use client";

import { ArrowRight, Building2, Lock } from "lucide-react";
import Link from "next/link";
import { useRef } from "react";
import { Button } from "@/components/ui/button";
import { BAND_COLORS, scoreBand } from "@/lib/score";
import { cityMap } from "./data/geo";
import { gsap, useGSAP } from "./motion";

const FIGURES = [
  { value: 271, suffix: " km", caption: "of bike lanes in Barcelona" },
  { value: 315000, suffix: "", caption: "bike & scooter trips a day, planned blind" },
  { value: 0, suffix: "", caption: "counters measure the ride itself" },
];

const BARS = [38, 52, 47, 61, 58, 66, 72, 69, 77, 74, 81, 86];

function DashboardPreview() {
  const kpis = [
    ["Streets measured", "140.8", "km"],
    ["Rides this week", "8,412", ""],
    ["Surface index", "71.4", "/100"],
    ["Hard-brake hotspots", "37", ""],
  ];
  return (
    <div className="overflow-hidden rounded-[22px] border border-white/10 bg-asphalt-950 text-left shadow-[0_60px_140px_-50px_rgb(0_0_0/1)]">
      <div className="flex items-center gap-2 border-b border-white/8 px-4 py-2.5">
        <span className="flex gap-1.5" aria-hidden>
          <span className="size-2.5 rounded-full bg-white/15" />
          <span className="size-2.5 rounded-full bg-white/15" />
          <span className="size-2.5 rounded-full bg-white/15" />
        </span>
        <span className="ml-3 flex items-center gap-1.5 rounded-md bg-white/5 px-2 py-1 font-mono text-[10px] text-asphalt-300">
          <Lock className="size-3" /> city.umi.app/overview
        </span>
        <span className="ml-auto hidden rounded-full border border-white/10 px-2 py-0.5 font-mono text-[9px] text-asphalt-300 sm:block">ANONYMISED &amp; AGGREGATED</span>
      </div>
      <div className="grid gap-3 p-3 sm:p-4">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {kpis.map(([l, v, u]) => (
            <div key={l} className="rounded-xl border border-white/8 bg-asphalt-900 p-2.5 sm:p-3">
              <div className="truncate font-mono text-[8.5px] tracking-wider text-asphalt-400 uppercase sm:text-[9px]">{l}</div>
              <div className="mt-1 font-num text-base font-semibold text-paper sm:text-xl">
                {v}
                <span className="ml-0.5 text-[10px] font-normal text-asphalt-400">{u}</span>
              </div>
            </div>
          ))}
        </div>
        <div className="grid gap-2 sm:grid-cols-[1.4fr_1fr]">
          <div className="rounded-xl border border-white/8 bg-asphalt-900 p-2">
            <div className="flex items-center justify-between px-1 pb-1">
              <span className="font-mono text-[9px] tracking-wider text-asphalt-400 uppercase">Surface index by district</span>
            </div>
            <svg viewBox={`0 0 ${cityMap.width} ${cityMap.height}`} className="mx-auto h-auto max-h-[280px] w-full" aria-hidden>
              {cityMap.districts.map((d) => (
                <path key={d.name} d={d.d} fill={BAND_COLORS.dark[scoreBand(d.surfaceIndex)]} fillOpacity="0.82" stroke="#060a12" strokeWidth="2.5" />
              ))}
              {cityMap.districts.map((d) => (
                <text key={d.name} x={d.label[0]} y={d.label[1]} textAnchor="middle" fontFamily="var(--font-display)" fontWeight="700" fontSize="15" fill="#0b1220">
                  {Math.round(d.surfaceIndex)}
                </text>
              ))}
            </svg>
          </div>
          <div className="flex flex-col rounded-xl border border-white/8 bg-asphalt-900 p-3">
            <span className="font-mono text-[9px] tracking-wider text-asphalt-400 uppercase">Rides aggregated · 12 months</span>
            <div className="mt-3 flex h-24 items-end gap-1 sm:h-32">
              {BARS.map((b, i) => (
                <span key={i} className="flex-1 rounded-t-sm bg-lane/70" style={{ height: `${b}%` }} />
              ))}
            </div>
            <div className="mt-3 space-y-1.5">
              {[
                ["Diagonal × Pg. Sant Joan", 41],
                ["Pl. de les Glòries", 36],
                ["Pg. de Gràcia × Aragó", 31],
              ].map(([n, v]) => (
                <div key={n} className="flex items-center justify-between text-[10px]">
                  <span className="truncate text-asphalt-300">{n}</span>
                  <span className="font-num font-semibold text-signal">{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function ForCities() {
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        // switch into "data mode"
        gsap.fromTo(".city-mode", { opacity: 0 }, { opacity: 1, ease: "none", scrollTrigger: { trigger: root.current, start: "top 85%", end: "top 30%", scrub: true } });
        gsap.fromTo(".city-knob", { x: 0 }, { x: 16, ease: "power2.inOut", scrollTrigger: { trigger: root.current, start: "top 70%", end: "top 45%", scrub: true } });
        gsap.fromTo(
          ".city-dash",
          { rotateX: 34, rotateZ: -6, scale: 0.86, y: 60 },
          { rotateX: 0, rotateZ: 0, scale: 1, y: 0, ease: "none", scrollTrigger: { trigger: ".city-dash-wrap", start: "top 92%", end: "center 55%", scrub: 0.6 } },
        );
        gsap.utils.toArray<HTMLElement>(".city-figure").forEach((el) => {
          const target = Number(el.dataset.value);
          const counter = { v: 0 };
          const out = el.querySelector(".city-figure-value")!;
          gsap.to(counter, {
            v: target,
            duration: 1.6,
            ease: "expo.out",
            scrollTrigger: { trigger: el, start: "top 85%" },
            onUpdate: () => {
              out.textContent = Math.round(counter.v).toLocaleString("en-US");
            },
          });
        });
      });
    },
    { scope: root },
  );

  return (
    <section ref={root} id="cities" aria-labelledby="cities-title" className="relative overflow-hidden bg-asphalt-950 py-28 sm:py-36">
      <div
        aria-hidden
        className="city-mode absolute inset-0 [background-image:radial-gradient(rgb(135_148_171/0.22)_1px,transparent_1px)] [background-size:22px_22px] [mask-image:linear-gradient(to_bottom,transparent,black_20%,black_80%,transparent)]"
      />
      <div className="relative mx-auto max-w-6xl px-5 sm:px-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <div className="flex items-center gap-3">
              <p className="label-mono inline-flex items-center gap-2 text-lane-300">
                <Building2 className="size-3.5" /> UMI City Insights
              </p>
              <span className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] py-1 pr-1 pl-3 font-mono text-[10px] tracking-wider text-asphalt-300 uppercase" aria-hidden>
                Rider
                <span className="relative h-4 w-8 rounded-full bg-white/10">
                  <span className="city-knob absolute top-0.5 left-0.5 size-3 rounded-full bg-lane" />
                </span>
                <span className="pr-2">Data</span>
              </span>
            </div>
            <h2 id="cities-title" className="mt-3 font-display text-4xl font-semibold tracking-tight text-balance text-paper sm:text-6xl">
              For cities: measure the ride, not just the traffic.
            </h2>
            <p className="mt-5 max-w-xl text-lg leading-8 text-asphalt-200">
              Every Clip is a moving sensor. City Insights aggregates them into a surface index, hard-brake hotspots and hourly exposure maps — anonymised, with trip starts and ends trimmed, GDPR by design.
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <Button asChild variant="paper" size="lg" pill>
              <Link href="/city">
                Open the dashboard <ArrowRight />
              </Link>
            </Button>
            <Button asChild variant="glass" size="lg" pill>
              <Link href="/city/api">API docs</Link>
            </Button>
          </div>
        </div>

        <div className="city-dash-wrap mt-14 [perspective:1600px]">
          <div className="city-dash origin-top will-change-transform">
            <DashboardPreview />
          </div>
        </div>

        <dl className="mt-16 grid gap-8 border-t border-white/10 pt-10 sm:grid-cols-3">
          {FIGURES.map((f) => (
            <div key={f.caption} className="city-figure" data-value={f.value}>
              <dt className="sr-only">{f.caption}</dt>
              <dd>
                <span className="font-num text-5xl font-semibold tracking-tight text-paper sm:text-6xl">
                  <span className="city-figure-value">{f.value.toLocaleString("en-US")}</span>
                  {f.suffix}
                </span>
                <p className="mt-2 max-w-[16rem] text-asphalt-300">{f.caption}</p>
              </dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
