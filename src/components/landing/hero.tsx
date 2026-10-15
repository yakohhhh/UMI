"use client";

import { ArrowDown, ArrowRight, AudioLines, ShieldAlert, Waves, Wind } from "lucide-react";
import { useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { ClipDevice } from "./clip-device";
import { rideMap } from "./data/geo";
import { gsap, SplitText, useGSAP } from "./motion";

const CHIPS = [
  { icon: Wind, label: "PM2.5", value: "12 µg/m³", pos: "left-[6%] top-[14%]", delay: "0s" },
  { icon: Waves, label: "Comfort", value: "72", pos: "right-[5%] top-[8%]", delay: "-2s" },
  { icon: ShieldAlert, label: "Hard brake", value: "4.1 m/s²", pos: "left-[2%] top-[52%]", delay: "-4s" },
  { icon: AudioLines, label: "Noise", value: "61 dB", pos: "right-[1%] top-[44%]", delay: "-1s" },
];

/** Abstract Eixample grid (real Barcelona geometry) with a looping ride trace. */
function StreetGridBackdrop() {
  return (
    <svg
      viewBox={`0 0 ${rideMap.width} ${rideMap.height}`}
      preserveAspectRatio="xMidYMid slice"
      className="absolute inset-0 size-full"
      aria-hidden
    >
      <defs>
        <radialGradient id="hero-fade" cx="0.5" cy="0.45" r="0.62">
          <stop offset="0" stopColor="#fff" stopOpacity="1" />
          <stop offset="0.7" stopColor="#fff" stopOpacity="0.35" />
          <stop offset="1" stopColor="#fff" stopOpacity="0" />
        </radialGradient>
        <mask id="hero-mask">
          <rect width="100%" height="100%" fill="url(#hero-fade)" />
        </mask>
        <clipPath id="hero-city">
          <path d={rideMap.city} />
        </clipPath>
      </defs>
      <g mask="url(#hero-mask)">
        <g clipPath="url(#hero-city)" stroke="#8794ab" strokeOpacity="0.16" strokeWidth="0.8">
          {rideMap.grid.map((d, i) => (
            <path key={i} d={d} fill="none" />
          ))}
        </g>
        <path d={rideMap.city} fill="none" stroke="#8794ab" strokeOpacity="0.22" strokeWidth="1" />
        <path d={rideMap.diagonal} fill="none" stroke="#b6c0d0" strokeOpacity="0.28" strokeWidth="2.4" clipPath="url(#hero-city)" />
        <path d={rideMap.granVia} fill="none" stroke="#b6c0d0" strokeOpacity="0.2" strokeWidth="2" clipPath="url(#hero-city)" />
        <path d={rideMap.route} fill="none" stroke="#ff5b1f" strokeOpacity="0.18" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <path
          d={rideMap.route}
          pathLength={1}
          fill="none"
          stroke="#ff5b1f"
          strokeWidth="3"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="hero-trace"
        />
      </g>
    </svg>
  );
}

export function Hero() {
  const root = useRef<HTMLElement>(null);
  const tiltRef = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add({ motion: "(prefers-reduced-motion: no-preference)", reduce: "(prefers-reduced-motion: reduce)" }, (ctx) => {
        const { motion } = ctx.conditions as { motion: boolean };
        const split = SplitText.create(".hero-title", { type: "words", mask: "words", wordsClass: "will-change-transform" });
        if (!motion) {
          gsap.from([".hero-title", ".hero-fade"], { opacity: 0, duration: 0.6, stagger: 0.08 });
          return () => split.revert();
        }
        const tl = gsap.timeline({ delay: 0.15 });
        tl.from(split.words, { yPercent: 110, opacity: 0, duration: 1.1, stagger: 0.075 })
          .from(".hero-fade", { y: 24, opacity: 0, duration: 0.9, stagger: 0.08 }, "-=0.7")
          .from(".hero-device", { y: 80, opacity: 0, scale: 0.94, duration: 1.4 }, "-=1.1")
          .from(".hero-chip", { opacity: 0, scale: 0.9, duration: 0.8, stagger: 0.12 }, "-=0.8");

        // Leaving the hero: content drifts up and fades, the device sinks slightly.
        gsap.to([".hero-copy", ".hero-scroll"], {
          yPercent: -18,
          opacity: 0,
          ease: "none",
          scrollTrigger: { trigger: root.current, start: "top top", end: "bottom 30%", scrub: true },
        });
        gsap.to(".hero-device-wrap", {
          yPercent: 12,
          scale: 0.92,
          ease: "none",
          scrollTrigger: { trigger: root.current, start: "top top", end: "bottom top", scrub: true },
        });
        return () => split.revert();
      });
    },
    { scope: root },
  );

  // Pointer parallax on the device (transform only, eased in rAF).
  useEffect(() => {
    const el = tiltRef.current;
    const section = root.current;
    if (!el || !section || window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let tx = 0;
    let ty = 0;
    let x = 0;
    let y = 0;
    let raf = 0;
    const onMove = (e: PointerEvent) => {
      const r = section.getBoundingClientRect();
      tx = (e.clientX - r.left) / r.width - 0.5;
      ty = (e.clientY - r.top) / r.height - 0.5;
    };
    const loop = () => {
      x += (tx - x) * 0.06;
      y += (ty - y) * 0.06;
      el.style.transform = `rotateX(${10 - y * 14}deg) rotateY(${-26 + x * 22}deg)`;
      raf = requestAnimationFrame(loop);
    };
    section.addEventListener("pointermove", onMove);
    raf = requestAnimationFrame(loop);
    return () => {
      section.removeEventListener("pointermove", onMove);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <section ref={root} id="top" className="relative isolate flex min-h-[100svh] flex-col overflow-hidden bg-asphalt-900 ">
      <div aria-hidden className="absolute inset-0 translate-y-[14%] scale-110">
        <StreetGridBackdrop />
      </div>
      <div aria-hidden className="pointer-events-none absolute inset-x-0 top-0 h-[62%] bg-[radial-gradient(ellipse_60%_70%_at_50%_42%,rgb(11_18_32/0.92),rgb(11_18_32/0.55)_55%,transparent_80%)]" />
      <div aria-hidden className="pointer-events-none absolute inset-x-0 bottom-0 h-56 bg-gradient-to-b from-transparent to-asphalt-900" />
      <div aria-hidden className="pointer-events-none absolute bottom-[8%] left-1/2 h-80 w-80 -translate-x-1/2 rounded-full bg-signal/20 blur-[100px]" />
      <div className="hero-copy relative z-10 mx-auto flex w-full max-w-6xl flex-col items-center px-5 pt-28 text-center sm:pt-32">
        <p className="hero-fade label-mono inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.04] px-3 py-1.5 text-asphalt-200">
          <span className="size-1.5 rounded-full bg-signal" /> Urban Motion Intelligence · Barcelona
        </p>
        <h1 className="hero-title mt-6 max-w-5xl font-display text-[42px] leading-[1.02] font-semibold tracking-[-0.035em] text-balance text-paper sm:text-7xl lg:text-[84px]">
          Know the street before you take&nbsp;it.
        </h1>
        <p className="hero-fade mt-6 max-w-xl text-base leading-7 text-asphalt-200 sm:text-lg">
          A matchbox-sized sensor that clips on your bike, scooter or running belt and measures every street you take: comfort, safety, air and noise.
        </p>
        <div className="hero-fade mt-8 flex flex-col items-center gap-3 sm:flex-row">
          <Button asChild size="xl" pill>
            <a href="#preorder">
              Pre-order — €99 <ArrowRight />
            </a>
          </Button>
          <Button asChild variant="glass" size="xl" pill>
            <a href="#how-it-works">See how it works</a>
          </Button>
        </div>
        <p className="hero-fade mt-4 text-xs text-asphalt-300">Early-bird price for the first 600 riders · €119 after · Ships spring 2027</p>
      </div>

      <div className="hero-device-wrap relative z-0 mx-auto mt-4 flex w-full max-w-4xl flex-1 items-start justify-center pb-24">
        <div className="hero-device relative [perspective:1200px]" role="img" aria-label="The UMI Clip, a small graphite sensor with an orange status light">
          <div className="animate-float [transform-style:preserve-3d]">
            <div ref={tiltRef} className="[transform-style:preserve-3d]" style={{ transform: "rotateX(10deg) rotateY(-26deg)" }}>
              <ClipDevice className="scale-[0.8] lg:scale-[0.9]" />
            </div>
          </div>
          <div aria-hidden className="mx-auto mt-10 h-5 w-40 rounded-[50%] bg-black/60 blur-xl" />
        </div>
        <div aria-hidden className="absolute inset-0 hidden md:block">
          {CHIPS.map((c) => (
            <div key={c.label} className={`hero-chip absolute ${c.pos}`}>
              <div className="animate-float" style={{ animationDelay: c.delay, animationDuration: "7s" }}>
                <div className="flex items-center gap-2.5 rounded-2xl border border-white/10 bg-asphalt-800/70 px-3 py-2 shadow-[0_18px_40px_-20px_rgb(0_0_0/0.9)] backdrop-blur-md">
                  <c.icon className="size-4 text-signal" />
                  <span className="label-mono text-asphalt-300">{c.label}</span>
                  <span className="font-num text-sm font-semibold text-paper">{c.value}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <a
        href="#product"
        className="hero-fade hero-scroll absolute bottom-6 left-1/2 z-10 hidden -translate-x-1/2 flex-col items-center gap-2 text-asphalt-300 transition-colors hover:text-paper sm:flex"
        aria-label="Scroll to the product"
      >
        <span className="label-mono">Scroll</span>
        <span className="relative h-9 w-[22px] rounded-full border border-white/20">
          <span className="absolute top-1.5 left-1/2 h-2 w-[3px] -translate-x-1/2 animate-[umi-scroll_1.8s_var(--ease-in-out-cubic)_infinite] rounded-full bg-signal" />
        </span>
        <ArrowDown className="sr-only" />
      </a>
    </section>
  );
}
