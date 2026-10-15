"use client";

import Lenis from "lenis";
import { createContext, useContext, useEffect, useRef, type ReactNode } from "react";
import { gsap, ScrollTrigger } from "./motion";

const LenisContext = createContext<{ scrollTo: (target: string | number) => void }>({
  scrollTo: (target) => {
    if (typeof target === "number") window.scrollTo({ top: target, behavior: "smooth" });
    else document.querySelector(target)?.scrollIntoView({ behavior: "smooth" });
  },
});

export const useSmoothScroll = () => useContext(LenisContext);

/**
 * Lenis smooth scroll, driven by GSAP's ticker so ScrollTrigger and Lenis
 * share one clock. Disabled when the user prefers reduced motion.
 */
export function SmoothScroll({ children }: { children: ReactNode }) {
  const lenisRef = useRef<Lenis | null>(null);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const lenis = new Lenis({ lerp: 0.09, smoothWheel: true, wheelMultiplier: 0.95, touchMultiplier: 1.4 });
    lenisRef.current = lenis;
    lenis.on("scroll", ScrollTrigger.update);
    const tick = (time: number) => lenis.raf(time * 1000);
    gsap.ticker.add(tick);
    gsap.ticker.lagSmoothing(0);

    // In-page anchors go through Lenis so pinned sections stay in sync.
    const onClick = (e: MouseEvent) => {
      const a = (e.target as HTMLElement).closest<HTMLAnchorElement>('a[href^="#"]');
      if (!a || a.getAttribute("href") === "#") return;
      const el = document.querySelector(a.getAttribute("href")!);
      if (!el) return;
      e.preventDefault();
      lenis.scrollTo(el as HTMLElement, { offset: -8, duration: 1.4 });
    };
    document.addEventListener("click", onClick);
    return () => {
      document.removeEventListener("click", onClick);
      gsap.ticker.remove(tick);
      lenis.destroy();
      lenisRef.current = null;
    };
  }, []);

  return (
    <LenisContext.Provider
      value={{
        scrollTo: (target) => {
          if (lenisRef.current) lenisRef.current.scrollTo(target as never, { offset: -8, duration: 1.4 });
          else if (typeof target === "number") window.scrollTo({ top: target });
          else document.querySelector(target)?.scrollIntoView();
        },
      }}
    >
      {children}
    </LenisContext.Provider>
  );
}
