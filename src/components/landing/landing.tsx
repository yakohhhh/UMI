"use client";

import { useEffect, useRef } from "react";
import { Dimensions } from "./dimensions";
import { ExplodedView } from "./exploded-view";
import { FinalCta, Footer } from "./final-cta";
import { ForCities } from "./for-cities";
import { Hero } from "./hero";
import { HowItWorks } from "./how-it-works";
import { Navbar } from "./navbar";
import { OneRide } from "./one-ride";
import { PhoneShowcase } from "./phone-showcase";
import { Pricing } from "./pricing";
import { Quotes } from "./quotes";
import { SmoothScroll } from "./smooth-scroll";

export function Landing() {
  const mainRef = useRef<HTMLElement>(null);

  // Looping CSS animations (trace, floats, viz loops) pause in sections that are
  // off screen, so the compositor only works on what is visible (see globals.css).
  useEffect(() => {
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) e.target.toggleAttribute("data-offscreen", !e.isIntersecting);
    });
    mainRef.current?.querySelectorAll("section").forEach((s) => io.observe(s));
    return () => io.disconnect();
  }, []);

  return (
    <SmoothScroll>
        <div className="dark overflow-x-clip bg-asphalt-900 text-paper">
          <a href="#main" className="sr-only z-[60] rounded-lg bg-signal px-3 py-2 text-asphalt-900 focus:not-sr-only focus:fixed focus:top-3 focus:left-3">
            Skip to content
          </a>
          <Navbar />
          <main ref={mainRef} id="main">
            <Hero />
            <ExplodedView />
            <OneRide />
            <Dimensions />
            <PhoneShowcase />
            <Quotes />
            <ForCities />
            <HowItWorks />
            <Pricing />
            <FinalCta />
          </main>
          <Footer />
        </div>
    </SmoothScroll>
  );
}
