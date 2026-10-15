"use client";

import { ArrowRight, Check } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { Logo } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import { gsap, useGSAP } from "./motion";
import { useRef } from "react";

export function FinalCta() {
  const root = useRef<HTMLElement>(null);
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "sending" | "done" | "invalid">("idle");

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add("(prefers-reduced-motion: no-preference)", () => {
        gsap.from(".cta-reveal", { y: 40, opacity: 0, stagger: 0.1, duration: 1, scrollTrigger: { trigger: root.current, start: "top 70%" } });
      });
    },
    { scope: root },
  );

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setStatus("invalid");
      return;
    }
    setStatus("sending");
    setTimeout(() => setStatus("done"), 700);
  };

  return (
    <section ref={root} id="preorder" aria-labelledby="cta-title" className="relative overflow-hidden bg-asphalt-900 py-28 sm:py-40">
      <div aria-hidden className="absolute top-1/2 left-1/2 h-[520px] w-[820px] -translate-x-1/2 -translate-y-1/2 rounded-full bg-signal/20 blur-[140px]" />
      <div className="relative mx-auto max-w-3xl px-5 text-center sm:px-8">
        <p className="cta-reveal label-mono text-signal">Early bird · €99</p>
        <h2 id="cta-title" className="cta-reveal mt-4 font-display text-4xl leading-[1.05] font-semibold tracking-tight text-balance text-paper sm:text-6xl">
          Be one of the first 600 riders mapping Barcelona.
        </h2>
        <p className="cta-reveal mx-auto mt-5 max-w-lg text-lg text-asphalt-200">
          Reserve your Clip today. You pay when it ships in spring 2027 — and every ride you take makes the map better for everyone.
        </p>
        {status === "done" ? (
          <div role="status" className="cta-reveal mx-auto mt-10 flex max-w-md items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.04] p-4 text-left">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-full bg-signal text-asphalt-900">
              <Check className="size-5" />
            </span>
            <p className="text-sm text-asphalt-100">
              You&apos;re on the list. We&apos;ll write to <strong className="text-paper">{email}</strong> before the first batch ships.
            </p>
          </div>
        ) : (
          <form onSubmit={submit} className="cta-reveal mx-auto mt-10 flex max-w-md flex-col gap-3 sm:flex-row" noValidate>
            <label htmlFor="cta-email" className="sr-only">
              Email address
            </label>
            <input
              id="cta-email"
              type="email"
              inputMode="email"
              autoComplete="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (status === "invalid") setStatus("idle");
              }}
              aria-invalid={status === "invalid"}
              aria-describedby="cta-hint"
              className="h-14 flex-1 rounded-full border border-white/12 bg-white/[0.05] px-6 text-paper placeholder:text-asphalt-400 focus-visible:border-signal/60 focus-visible:ring-4 focus-visible:ring-signal/20 focus-visible:outline-none"
            />
            <Button type="submit" size="xl" pill disabled={status === "sending"}>
              {status === "sending" ? "Reserving…" : "Pre-order"} <ArrowRight />
            </Button>
          </form>
        )}
        <p id="cta-hint" className={`cta-reveal mt-4 text-xs ${status === "invalid" ? "text-signal" : "text-asphalt-400"}`}>
          {status === "invalid" ? "That email doesn't look right — check for a typo." : "No payment today. Unsubscribe in one click."}
        </p>
      </div>
    </section>
  );
}

const FOOTER = [
  { title: "Product", links: [["UMI Clip", "#product"], ["How it works", "#how-it-works"], ["Pricing", "#pricing"], ["Open the app", "/app"]] },
  { title: "Cities", links: [["City Insights", "/city"], ["API", "/city/api"], ["Data ethics", "/city/api#privacy"]] },
  { title: "Company", links: [["About", "#top"], ["Press kit", "#top"], ["Contact", "mailto:hola@umi.city"]] },
];

export function Footer() {
  return (
    <footer className="border-t border-white/8 bg-asphalt-950 text-asphalt-300">
      <div className="mx-auto grid max-w-6xl gap-10 px-5 py-14 sm:px-8 md:grid-cols-[1.4fr_repeat(3,1fr)]">
        <div>
          <Logo className="h-6 text-paper" />
          <p className="mt-4 max-w-xs text-sm leading-6">Urban Motion Intelligence. Know the street before you take it. Made in Barcelona.</p>
        </div>
        {FOOTER.map((col) => (
          <nav key={col.title} aria-label={col.title}>
            <h3 className="label-mono text-asphalt-400">{col.title}</h3>
            <ul className="mt-4 space-y-2.5 text-sm">
              {col.links.map(([label, href]) => (
                <li key={label}>
                  {href.startsWith("/") ? (
                    <Link href={href} className="transition-colors hover:text-paper">
                      {label}
                    </Link>
                  ) : (
                    <a href={href} className="transition-colors hover:text-paper">
                      {label}
                    </a>
                  )}
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>
      <div className="border-t border-white/8">
        <div className="mx-auto flex max-w-6xl flex-col gap-2 px-5 py-6 text-xs sm:flex-row sm:items-center sm:justify-between sm:px-8">
          <p>© 2026 UMI — Urban Motion Intelligence, Barcelona.</p>
          <p>Shared data is anonymised and aggregated. Trip starts and ends are trimmed.</p>
        </div>
      </div>
    </footer>
  );
}
