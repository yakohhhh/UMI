"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { Menu, X } from "lucide-react";
import { Logo } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "#product", label: "Product" },
  { href: "#how-it-works", label: "How it works" },
  { href: "#cities", label: "For cities" },
  { href: "#pricing", label: "Pricing" },
];

/** Fixed navbar: blurs and tightens after the first scroll; thin orange progress bar on top. */
export function Navbar() {
  const barRef = useRef<HTMLDivElement>(null);
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    let raf = 0;
    const update = () => {
      raf = 0;
      const max = document.documentElement.scrollHeight - window.innerHeight;
      if (barRef.current) barRef.current.style.transform = `scaleX(${max > 0 ? window.scrollY / max : 0})`;
      setScrolled(window.scrollY > 24);
    };
    const onScroll = () => {
      if (!raf) raf = requestAnimationFrame(update);
    };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    // pinned sections change the document height once ScrollTrigger has measured them
    const t = window.setTimeout(update, 600);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      cancelAnimationFrame(raf);
      window.clearTimeout(t);
    };
  }, []);

  useEffect(() => {
    document.documentElement.style.overflow = open ? "hidden" : "";
    return () => {
      document.documentElement.style.overflow = "";
    };
  }, [open]);

  return (
    <header className="fixed inset-x-0 top-0 z-50">
      <div ref={barRef} aria-hidden className="absolute inset-x-0 top-0 h-[2px] origin-left scale-x-0 bg-signal will-change-transform" />
      <div className={cn("mx-auto px-4 transition-[padding] duration-500 ease-out-expo sm:px-6", scrolled ? "max-w-5xl pt-3" : "max-w-7xl pt-4")}>
        <nav
          aria-label="Main"
          className={cn(
            "relative flex items-center justify-between rounded-2xl px-3 transition-[background-color,border-color,box-shadow,height] duration-500 ease-out-expo sm:px-4",
            scrolled
              ? "h-14 border border-white/10 bg-asphalt-900/70 shadow-[0_12px_40px_-18px_rgb(0_0_0/0.8)] backdrop-blur-xl backdrop-saturate-150"
              : "h-16 border border-transparent",
          )}
        >
          <Link href="/" aria-label="UMI home" className="flex items-center gap-2 rounded-lg px-1 text-paper">
            <Logo className="h-[22px]" />
          </Link>
          <ul className="hidden items-center gap-1 md:flex">
            {LINKS.map((l) => (
              <li key={l.href}>
                <a href={l.href} className="rounded-lg px-3 py-2 text-[13px] text-asphalt-200 transition-colors hover:text-paper">
                  {l.label}
                </a>
              </li>
            ))}
          </ul>
          <div className="flex items-center gap-2">
            <Link href="/app" className="hidden rounded-lg px-3 py-2 text-[13px] text-asphalt-200 transition-colors hover:text-paper sm:block">
              Open the app
            </Link>
            <Button asChild size="sm" pill className="hidden h-9 px-4 sm:inline-flex">
              <a href="#preorder">Pre-order</a>
            </Button>
            <button
              type="button"
              className="inline-flex size-10 items-center justify-center rounded-xl text-paper md:hidden"
              aria-expanded={open}
              aria-controls="mobile-menu"
              aria-label={open ? "Close menu" : "Open menu"}
              onClick={() => setOpen((o) => !o)}
            >
              {open ? <X className="size-5" /> : <Menu className="size-5" />}
            </button>
          </div>
        </nav>
      </div>
      <div
        id="mobile-menu"
        hidden={!open}
        className="fixed inset-x-0 top-0 -z-10 h-[100svh] bg-asphalt-950/95 px-6 pt-28 backdrop-blur-xl md:hidden"
      >
        <ul className="flex flex-col gap-1">
          {[...LINKS, { href: "#preorder", label: "Pre-order — €99" }].map((l) => (
            <li key={l.href}>
              <a href={l.href} onClick={() => setOpen(false)} className="block border-b border-white/8 py-4 font-display text-2xl text-paper">
                {l.label}
              </a>
            </li>
          ))}
          <li>
            <Link href="/app" className="block py-4 font-display text-2xl text-signal" onClick={() => setOpen(false)}>
              Open the app →
            </Link>
          </li>
        </ul>
      </div>
    </header>
  );
}
