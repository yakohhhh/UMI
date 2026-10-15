"use client";

import { AlertTriangle, CircleDot, Wind } from "lucide-react";
import { useRef } from "react";
import { BAND_COLORS, scoreBand } from "@/lib/score";
import { rideMap } from "./data/geo";
import { gsap, useGSAP } from "./motion";

const SCORES = [
  { key: "comfort", label: "Comfort" },
  { key: "safety", label: "Safety" },
  { key: "air", label: "Air" },
  { key: "noise", label: "Noise" },
] as const;

const EVENT_META = {
  hard_brake: { title: "Hard brake", icon: AlertTriangle, unit: "m/s²", color: "#ff5b1f" },
  pothole: { title: "Pothole", icon: CircleDot, unit: "m/s² peak", color: "#f5c542" },
  pm_spike: { title: "PM2.5 spike", icon: Wind, unit: "µg/m³", color: "#ff5b1f" },
  noise_peak: { title: "Noise peak", icon: Wind, unit: "dB", color: "#f5c542" },
} as const;

const START_MIN = 7 * 60 + 52;

/** Where each callout sits relative to its marker, chosen so it never hides the route. */
const PLACEMENT: Record<string, { x: string; y: "above" | "below" }> = {
  hard_brake: { x: "-50%", y: "below" },
  pothole: { x: "-62%", y: "above" },
  pm_spike: { x: "-46%", y: "above" },
  noise_peak: { x: "-50%", y: "below" },
};

export function OneRide() {
  const root = useRef<HTMLElement>(null);
  const routeRef = useRef<SVGPathElement>(null);
  const glowRef = useRef<SVGPathElement>(null);
  const riderRef = useRef<SVGGElement>(null);
  const clockRef = useRef<HTMLSpanElement>(null);
  const distRef = useRef<HTMLSpanElement>(null);
  const scoreRefs = useRef<(HTMLSpanElement | null)[]>([]);
  const barRefs = useRef<(HTMLDivElement | null)[]>([]);
  const eventRefs = useRef<(SVGGElement | null)[]>([]);
  const calloutRefs = useRef<(HTMLDivElement | null)[]>([]);

  const { ride, events } = rideMap;

  useGSAP(
    () => {
      const path = routeRef.current!;
      const total = path.getTotalLength();
      const state = { p: 0 };
      const shown = events.map(() => false);

      const apply = () => {
        const p = state.p;
        path.style.strokeDashoffset = String(1 - p);
        if (glowRef.current) glowRef.current.style.strokeDashoffset = String(1 - p);
        const pt = path.getPointAtLength(total * p);
        riderRef.current?.setAttribute("transform", `translate(${pt.x} ${pt.y})`);
        const minutes = START_MIN + p * ride.durationMin;
        if (clockRef.current) clockRef.current.textContent = `${String(Math.floor(minutes / 60)).padStart(2, "0")}:${String(Math.floor(minutes % 60)).padStart(2, "0")}`;
        if (distRef.current) distRef.current.textContent = (p * ride.distanceKm).toFixed(1);
        const eased = 1 - Math.pow(1 - p, 2.2);
        SCORES.forEach((s, i) => {
          const v = Math.round(ride.scores[s.key] * eased);
          const el = scoreRefs.current[i];
          if (el) el.textContent = String(v);
          const bar = barRefs.current[i];
          if (bar) bar.style.transform = `scaleX(${v / 100})`;
        });
        events.forEach((e, i) => {
          const on = p >= e.at;
          if (on === shown[i]) return;
          shown[i] = on;
          gsap.to(eventRefs.current[i], { scale: on ? 1 : 0, opacity: on ? 1 : 0, duration: 0.5, ease: on ? "back.out(2.4)" : "power2.in", transformOrigin: "center" });
          gsap.to(calloutRefs.current[i], { opacity: on ? 1 : 0, y: on ? 0 : 10, duration: 0.5, ease: "expo.out" });
        });
      };

      const mm = gsap.matchMedia();
      mm.add({ desktop: "(min-width: 1024px) and (prefers-reduced-motion: no-preference)", mobile: "(max-width: 1023px) and (prefers-reduced-motion: no-preference)", reduce: "(prefers-reduced-motion: reduce)" }, (ctx) => {
        const { desktop, reduce } = ctx.conditions as Record<string, boolean>;
        if (reduce) {
          state.p = 1;
          apply();
          return;
        }
        state.p = 0;
        apply();
        gsap.to(state, {
          p: 1,
          ease: "none",
          onUpdate: apply,
          scrollTrigger: desktop
            ? { trigger: root.current, start: "top top", end: "+=240%", pin: true, scrub: 0.8, anticipatePin: 1 }
            : { trigger: ".ride-map", start: "top 70%", end: "bottom 25%", scrub: 0.6 },
        });
      });
    },
    { scope: root },
  );

  return (
    <section ref={root} aria-labelledby="ride-title" className="relative min-h-[100svh] overflow-hidden bg-asphalt-900 py-24 lg:flex lg:h-[100svh] lg:items-center lg:py-0">
      <div className="mx-auto grid w-full max-w-7xl items-center gap-10 px-5 sm:px-8 lg:grid-cols-[minmax(0,5fr)_minmax(0,7fr)] lg:gap-14">
        <div>
          <p className="label-mono text-signal">One ride</p>
          <h2 id="ride-title" className="mt-3 font-display text-4xl font-semibold tracking-tight text-balance text-paper sm:text-5xl">
            Gràcia → 22@. Every metre, measured.
          </h2>
          <p className="mt-4 max-w-md text-asphalt-200">
            Laia's commute on Thursday morning: {ride.distanceKm} km through Pg. de Sant Joan, Diagonal and Glòries. The Clip turns it into four scores and three moments worth knowing.
          </p>

          <dl className="mt-8 grid max-w-md grid-cols-2 gap-4">
            <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
              <dt className="label-mono text-asphalt-300">Clock</dt>
              <dd className="mt-1 font-num text-3xl font-semibold text-paper">
                <span ref={clockRef}>07:52</span>
              </dd>
            </div>
            <div className="rounded-2xl border border-white/8 bg-white/[0.03] p-4">
              <dt className="label-mono text-asphalt-300">Distance</dt>
              <dd className="mt-1 font-num text-3xl font-semibold text-paper">
                <span ref={distRef}>0.0</span>
                <span className="ml-1 text-base text-asphalt-300">km</span>
              </dd>
            </div>
          </dl>

          <ul className="mt-4 grid max-w-md grid-cols-2 gap-x-6 gap-y-4" aria-label={`Ride scores: ${SCORES.map((s) => `${s.label} ${ride.scores[s.key]}`).join(", ")}`}>
            {SCORES.map((s, i) => (
              <li key={s.key} aria-hidden>
                <div className="flex items-baseline justify-between">
                  <span className="text-sm text-asphalt-200">{s.label}</span>
                  <span className="font-num text-2xl font-semibold text-paper">
                    <span
                      ref={(el) => {
                        scoreRefs.current[i] = el;
                      }}
                    >
                      0
                    </span>
                    <span className="text-xs text-asphalt-400">/100</span>
                  </span>
                </div>
                <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-white/8">
                  <div
                    ref={(el) => {
                      barRefs.current[i] = el;
                    }}
                    className="h-full origin-left scale-x-0 rounded-full"
                    style={{ background: BAND_COLORS.dark[scoreBand(ride.scores[s.key])] }}
                  />
                </div>
              </li>
            ))}
          </ul>
        </div>

        <div className="ride-map relative">
          <div className="relative overflow-hidden rounded-[28px] border border-white/10 bg-asphalt-950 shadow-[0_40px_120px_-40px_rgb(0_0_0/0.9)]">
            <svg viewBox={`0 0 ${rideMap.width} ${rideMap.height}`} className="block h-auto w-full" role="img" aria-label="Map of the ride from Gràcia to 22@ in Barcelona, with a hard brake on Diagonal, a pothole and a PM2.5 spike at Glòries.">
              <defs>
                <clipPath id="ride-city">
                  <path d={rideMap.city} />
                </clipPath>
                <filter id="ride-glow" x="-20%" y="-20%" width="140%" height="140%">
                  <feGaussianBlur stdDeviation="6" />
                </filter>
              </defs>
              <rect width="100%" height="100%" fill="#060a12" />
              <path d={rideMap.city} fill="#0d1524" />
              <g clipPath="url(#ride-city)">
                <g stroke="#3a4a66" strokeOpacity="0.55" strokeWidth="0.7">
                  {rideMap.grid.map((d, i) => (
                    <path key={i} d={d} fill="none" />
                  ))}
                </g>
                {rideMap.districts.map((d) => (
                  <path key={d.name} d={d.d} fill="none" stroke="#5b6b86" strokeOpacity="0.5" strokeWidth="1.2" strokeDasharray="4 4" />
                ))}
                <path d={rideMap.diagonal} fill="none" stroke="#8794ab" strokeOpacity="0.7" strokeWidth="3" />
                <path d={rideMap.granVia} fill="none" stroke="#8794ab" strokeOpacity="0.5" strokeWidth="2.4" />
              </g>
              {rideMap.labels.map((l) => (
                <text key={l.name} x={l.x} y={l.y} textAnchor="middle" fontFamily="var(--font-mono)" fontSize="13" letterSpacing="3" fill="#8794ab" fillOpacity="0.8">
                  {l.name}
                </text>
              ))}
              <path d={rideMap.route} fill="none" stroke="#ff5b1f" strokeOpacity="0.14" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" />
              <path ref={glowRef} d={rideMap.route} fill="none" stroke="#ff5b1f" strokeWidth="14" strokeOpacity="0.35" filter="url(#ride-glow)" pathLength={1} strokeDasharray="1" style={{ strokeDashoffset: 1 }} />
              <path ref={routeRef} d={rideMap.route} fill="none" stroke="#ff5b1f" strokeWidth="5" strokeLinecap="round" strokeLinejoin="round" pathLength={1} strokeDasharray="1" style={{ strokeDashoffset: 1 }} />
              <circle cx={rideMap.start[0]} cy={rideMap.start[1]} r="7" fill="#0b1220" stroke="#f6f4ef" strokeWidth="3" />
              <circle cx={rideMap.end[0]} cy={rideMap.end[1]} r="7" fill="#f6f4ef" />
              {events.map((e, i) => (
                <g
                  key={e.type}
                  ref={(el) => {
                    eventRefs.current[i] = el;
                  }}
                  style={{ opacity: 0, transformBox: "fill-box", transformOrigin: "center" }}
                >
                  <circle cx={e.x} cy={e.y} r="18" fill={EVENT_META[e.type as keyof typeof EVENT_META].color} fillOpacity="0.18" />
                  <circle cx={e.x} cy={e.y} r="8" fill={EVENT_META[e.type as keyof typeof EVENT_META].color} stroke="#060a12" strokeWidth="3" />
                </g>
              ))}
              <g ref={riderRef} transform={`translate(${rideMap.start[0]} ${rideMap.start[1]})`}>
                <circle r="16" fill="#ff5b1f" fillOpacity="0.25" className="animate-pulse-dot" style={{ transformBox: "fill-box", transformOrigin: "center" }} />
                <circle r="7.5" fill="#ff5b1f" stroke="#fff" strokeWidth="3" />
              </g>
            </svg>
            <div className="pointer-events-none absolute top-4 left-4 flex items-center gap-2 rounded-full border border-white/10 bg-asphalt-900/80 px-3 py-1.5 backdrop-blur">
              <span className="size-2 rounded-full bg-signal" />
              <span className="label-mono text-asphalt-200">Live replay · Thu {ride.start}</span>
            </div>
          </div>
          {/* callouts, positioned in % of the map */}
          {events.map((e, i) => {
            const meta = EVENT_META[e.type as keyof typeof EVENT_META];
            const left = (e.x / rideMap.width) * 100;
            const top = (e.y / rideMap.height) * 100;
            const place = PLACEMENT[e.type] ?? PLACEMENT.noise_peak;
            const below = place.y === "below";
            return (
              <div
                key={e.type}
                className="pointer-events-none absolute z-10 w-max"
                style={{ left: `${left}%`, top: `${top}%`, transform: `translate(${place.x}, ${below ? "26px" : "calc(-100% - 26px)"})` }}
              >
                <div
                  ref={(el) => {
                    calloutRefs.current[i] = el;
                  }}
                  className="rounded-2xl border border-white/10 bg-asphalt-800/90 px-3.5 py-2.5 opacity-0 shadow-[0_20px_40px_-20px_rgb(0_0_0/0.9)] backdrop-blur-md"
                >
                  <div className="flex items-center gap-2">
                    <meta.icon className="size-3.5" style={{ color: meta.color }} aria-hidden />
                    <span className="text-[13px] font-semibold text-paper">
                      {meta.title}
                      {e.type === "pm_spike" ? ` at ${Number(e.time.slice(0, 2))}:${e.time.slice(3)}` : ""}
                    </span>
                    <span className="font-mono text-[11px] text-asphalt-300">{e.time}</span>
                  </div>
                  <p className="mt-0.5 text-xs text-asphalt-300">
                    <span className="font-num font-semibold text-paper">{e.value}</span> {meta.unit} · {e.street}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
