"use client";

import { useRef } from "react";
import { BrakeViz, NoiseViz, ParticlesViz, VibrationViz } from "./dimension-viz";
import { gsap, useGSAP } from "./motion";

const PANELS = [
  {
    n: "01",
    key: "Comfort",
    title: "Smooth asphalt or rattling cobbles?",
    body: "The IMU samples vibration 100 times a second. UMI turns it into a comfort score per street, so you can tell a fresh bike lane from a patched one before your wrists do.",
    facts: ["6-axis IMU · 100 Hz", "m/s² RMS"],
    reading: { label: "Carrer d'Aragó", value: "1.8 m/s²", note: "Bumpy" },
    accent: "#3d9bff",
    Viz: VibrationViz,
  },
  {
    n: "02",
    key: "Safety",
    title: "Where riders brake hard, something is wrong.",
    body: "Every deceleration over 3 m/s² is logged with its place and time. When dozens of riders brake at the same corner, the corner is the problem — not the riders.",
    facts: ["Decelerations > 3 m/s²", "Impacts & near-stops"],
    reading: { label: "Diagonal × Pg. de Sant Joan", value: "41 / week", note: "Hotspot" },
    accent: "#ff5b1f",
    Viz: BrakeViz,
  },
  {
    n: "03",
    key: "Air",
    title: "What you breathe, street by street.",
    body: "A laser particle sensor reads PM2.5 every 10 seconds. Same street, different hour: the morning rush can double what you breathe on the way to work.",
    facts: ["Laser scattering · 10 s", "µg/m³ · EU 2030 limit 10"],
    reading: { label: "Pg. de Sant Joan, 8 am", value: "21 µg/m³", note: "Moderate" },
    accent: "#f5c542",
    Viz: ParticlesViz,
  },
  {
    n: "04",
    key: "Noise",
    title: "Loud streets are tiring streets.",
    body: "The MEMS microphone measures sound level in dB(A) and nothing else — audio is never recorded or stored. Quiet routes exist; now you can find them.",
    facts: ["MEMS mic · dB(A) only", "WHO guideline 53 dB"],
    reading: { label: "Av. Diagonal at 6 pm", value: "68 dB(A)", note: "Busy" },
    accent: "#8cb8ff",
    Viz: NoiseViz,
  },
];

export function Dimensions() {
  const root = useRef<HTMLElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(min-width: 1024px) and (prefers-reduced-motion: no-preference)", () => {
        const track = trackRef.current!;
        const distance = () => track.scrollWidth - window.innerWidth;
        const tween = gsap.to(track, {
          x: () => -distance(),
          ease: "none",
          scrollTrigger: {
            trigger: root.current,
            start: "top top",
            end: () => `+=${distance()}`,
            pin: true,
            scrub: 0.7,
            invalidateOnRefresh: true,
            anticipatePin: 1,
          },
        });
        gsap.to(".dim-progress", { scaleX: 1, ease: "none", scrollTrigger: { trigger: root.current, start: "top top", end: () => `+=${distance()}`, scrub: true } });
        gsap.utils.toArray<HTMLElement>(".dim-panel").forEach((panel) => {
          gsap.from(panel.querySelectorAll(".dim-reveal"), {
            y: 30,
            opacity: 0,
            stagger: 0.08,
            duration: 0.9,
            scrollTrigger: { trigger: panel, containerAnimation: tween, start: "left 75%", toggleActions: "play none none reverse" },
          });
        });
      });
      mm.add("(max-width: 1023px) and (prefers-reduced-motion: no-preference)", () => {
        gsap.utils.toArray<HTMLElement>(".dim-panel").forEach((panel) => {
          gsap.from(panel, { y: 40, opacity: 0, duration: 0.9, scrollTrigger: { trigger: panel, start: "top 85%" } });
        });
      });
    },
    { scope: root },
  );

  return (
    <section ref={root} aria-labelledby="dims-title" className="relative overflow-hidden bg-asphalt-950 lg:motion-safe:h-[100svh]">
      <div className="mx-auto max-w-7xl px-5 pt-24 sm:px-8 lg:pt-20 lg:motion-safe:absolute lg:motion-safe:inset-x-0 lg:motion-safe:top-0 lg:motion-safe:z-10">
        <p className="label-mono text-signal">Four dimensions</p>
        <h2 id="dims-title" className="mt-3 max-w-2xl font-display text-4xl font-semibold tracking-tight text-paper sm:text-5xl">
          Four numbers for every street.
        </h2>
      </div>
      <div
        ref={trackRef}
        className="flex flex-col gap-5 px-5 pt-10 pb-24 sm:px-8 lg:items-center lg:gap-8 lg:motion-safe:h-full lg:motion-safe:flex-row lg:motion-safe:px-[max(32px,calc((100vw_-_80rem)/2_+_32px))] lg:motion-safe:pt-28 lg:motion-safe:pb-10"
      >
        {PANELS.map((p) => (
          <article
            key={p.key}
            className="dim-panel relative flex shrink-0 flex-col justify-between gap-8 overflow-hidden rounded-[28px] border border-white/8 bg-asphalt-900 p-6 sm:p-8 lg:h-[min(560px,68vh)] lg:w-[min(1040px,78vw)] lg:flex-row lg:items-center lg:gap-12 lg:p-12"
          >
            <div aria-hidden className="absolute -top-24 -right-24 size-72 rounded-full opacity-25 blur-[100px]" style={{ background: p.accent }} />
            <div className="relative max-w-md">
              <div className="dim-reveal flex items-center gap-3">
                <span className="font-mono text-sm text-asphalt-400">{p.n}</span>
                <span className="h-px w-8 bg-white/15" />
                <span className="label-mono" style={{ color: p.accent }}>
                  {p.key}
                </span>
              </div>
              <h3 className="dim-reveal mt-5 font-display text-3xl leading-tight font-semibold text-balance text-paper sm:text-4xl">{p.title}</h3>
              <p className="dim-reveal mt-4 leading-7 text-asphalt-200">{p.body}</p>
              <ul className="dim-reveal mt-6 flex flex-wrap gap-2">
                {p.facts.map((f) => (
                  <li key={f} className="rounded-full border border-white/10 px-3 py-1 font-mono text-[11px] text-asphalt-300">
                    {f}
                  </li>
                ))}
              </ul>
            </div>
            <div className="dim-reveal relative w-full max-w-[520px] lg:flex-1">
              <div className="rounded-2xl border border-white/8 bg-asphalt-950/70 p-4">
                <p.Viz />
              </div>
              <div className="mt-3 flex items-center justify-between rounded-2xl border border-white/8 bg-white/[0.03] px-4 py-3">
                <span className="text-sm text-asphalt-300">{p.reading.label}</span>
                <span className="flex items-baseline gap-2">
                  <span className="font-num text-lg font-semibold text-paper">{p.reading.value}</span>
                  <span className="text-xs" style={{ color: p.accent }}>
                    {p.reading.note}
                  </span>
                </span>
              </div>
            </div>
          </article>
        ))}
        <div aria-hidden className="hidden w-px shrink-0 lg:motion-safe:block" />
      </div>
      <div aria-hidden className="absolute inset-x-0 bottom-0 hidden h-[2px] bg-white/5 lg:motion-safe:block">
        <div className="dim-progress h-full origin-left scale-x-0 bg-signal/70" />
      </div>
    </section>
  );
}
