"use client";

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
import { TooltipProvider } from "@/components/ui/tooltip";

export function Landing() {
  return (
    <SmoothScroll>
      <TooltipProvider>
        <div className="dark overflow-x-clip bg-asphalt-900 text-paper">
          <a href="#main" className="sr-only z-[60] rounded-lg bg-signal px-3 py-2 text-asphalt-900 focus:not-sr-only focus:fixed focus:top-3 focus:left-3">
            Skip to content
          </a>
          <Navbar />
          <main id="main">
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
          <div aria-hidden className="pointer-events-none fixed inset-0 z-[70] opacity-[0.05] mix-blend-soft-light [background-image:url(/noise.png)] [background-size:180px_180px]" />
        </div>
      </TooltipProvider>
    </SmoothScroll>
  );
}
