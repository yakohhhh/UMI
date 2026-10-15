"use client";

import { useRef } from "react";
import { gsap, useGSAP } from "./motion";

type Part = string | { accent: string };

const QUOTES: { parts: Part[]; tag: string }[] = [
  { parts: ["This road is ", { accent: "fast but uncomfortable." }], tag: "Carrer d'Aragó · Comfort 41 · avg 24 km/h" },
  { parts: ["This junction has ", { accent: "many hard brakes." }], tag: "Diagonal × Pg. de Sant Joan · 41 hard brakes / week" },
  { parts: ["This bike lane is calm, but more polluted ", { accent: "at 8 am." }], tag: "Pg. de Sant Joan · PM2.5 21 µg/m³ at 8 am, 11 at 3 pm" },
  { parts: ["Best 5 km run now: ", { accent: "little traffic, clean air." }], tag: "Ciutadella → Passeig Marítim · Air 86 · right now" },
];

function words(parts: Part[]) {
  return parts.flatMap((p) => {
    const accent = typeof p !== "string";
    const text = typeof p === "string" ? p : p.accent;
    return text
      .split(" ")
      .filter(Boolean)
      .map((w) => ({ w, accent }));
  });
}

/** Keynote-style reveal: each word brightens as the scroll passes it. */
export function Quotes() {
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.utils.toArray<HTMLElement>(".q-block").forEach((block) => {
          const ws = block.querySelectorAll(".q-word");
          gsap.fromTo(
            ws,
            { opacity: 0.14 },
            { opacity: 1, ease: "none", stagger: 0.1, scrollTrigger: { trigger: block, start: "top 78%", end: "bottom 52%", scrub: true } },
          );
          gsap.fromTo(
            block.querySelector(".q-tag"),
            { opacity: 0, y: 12 },
            { opacity: 1, y: 0, ease: "none", scrollTrigger: { trigger: block, start: "top 50%", end: "top 35%", scrub: true } },
          );
        });
      });
    },
    { scope: root },
  );

  return (
    <section ref={root} aria-label="What UMI tells you" className="relative bg-asphalt-900 py-28 sm:py-40">
      <div className="mx-auto max-w-6xl space-y-24 px-5 sm:space-y-36 sm:px-8">
        {QUOTES.map((q, qi) => (
          <figure key={qi} className="q-block">
            <blockquote className="font-display text-[40px] leading-[1.05] font-semibold tracking-[-0.03em] text-balance sm:text-6xl lg:text-[84px]">
              <span className="sr-only">{q.parts.map((p) => (typeof p === "string" ? p : p.accent)).join("")}</span>
              <span aria-hidden>
                {words(q.parts).map((w, i) => (
                  <span key={i} className={`q-word inline-block ${w.accent ? "text-signal" : "text-paper"}`}>
                    {w.w}&nbsp;
                  </span>
                ))}
              </span>
            </blockquote>
            <figcaption className="q-tag mt-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 font-mono text-xs text-asphalt-300">
              <span className="size-1.5 rounded-full bg-signal" />
              {q.tag}
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}
