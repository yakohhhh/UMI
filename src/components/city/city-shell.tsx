"use client";

import { MotionConfig } from "framer-motion";
import { Activity, ArrowLeft, Code2, LayoutGrid, ShieldAlert, Waves, Wind, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { Logo } from "@/components/brand/logo";
import { ThemeToggle } from "@/components/shell/theme-toggle";
import { Avatar } from "@/components/ui/avatar";
import { TooltipProvider } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";
import { CityFiltersProvider, FilterBar } from "./city-filters";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export const CITY_NAV: NavItem[] = [
  { href: "/city", label: "Overview", icon: LayoutGrid },
  { href: "/city/surface", label: "Surface", icon: Waves },
  { href: "/city/safety", label: "Safety", icon: ShieldAlert },
  { href: "/city/air-noise", label: "Air & noise", icon: Wind },
  { href: "/city/api", label: "API", icon: Code2 },
];

function NavLinks({ pathname, className }: { pathname: string; className?: string }) {
  return (
    <ul className={cn("flex items-center gap-1", className)}>
      {CITY_NAV.map((item) => {
        const active = item.href === "/city" ? pathname === "/city" : pathname.startsWith(item.href);
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              aria-current={active ? "page" : undefined}
              className={cn(
                "relative inline-flex h-9 items-center gap-2 rounded-lg px-3 text-[13px] font-medium whitespace-nowrap transition-colors",
                active ? "bg-surface-2 text-fg" : "text-fg-muted hover:bg-surface-2/60 hover:text-fg",
              )}
            >
              <item.icon className={cn("size-4", active && "text-accent-ink")} aria-hidden />
              {item.label}
              {active ? <span aria-hidden className="absolute inset-x-3 -bottom-[9px] h-0.5 rounded-full bg-signal max-lg:hidden" /> : null}
            </Link>
          </li>
        );
      })}
    </ul>
  );
}

/**
 * City Insights "control room": dense header with navigation, shared filters
 * and the anonymisation promise always in view.
 */
export function CityShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <MotionConfig reducedMotion="user">
      <TooltipProvider>
        <CityFiltersProvider>
          <div className="min-h-dvh bg-bg text-fg">
            <a href="#city-main" className="sr-only z-50 rounded-lg bg-signal px-3 py-2 text-asphalt-900 focus:not-sr-only focus:fixed focus:top-3 focus:left-3">
              Skip to content
            </a>
            <header className="relative z-30 border-b border-line bg-bg/85 backdrop-blur-xl backdrop-saturate-150 lg:sticky lg:top-0">
              <div className="flex h-14 items-center gap-3 px-4 sm:px-6">
                <Link href="/city" className="flex items-center gap-2.5 rounded-lg text-fg" aria-label="UMI City Insights, overview">
                  <Logo className="h-5" />
                  <span className="label-mono hidden text-[10px] text-fg-subtle sm:inline">City Insights</span>
                </Link>
                <span className="mx-1 hidden h-5 w-px bg-line md:block" aria-hidden />
                <span className="hidden items-center gap-2 text-xs text-fg-muted md:flex">
                  <Activity className="size-3.5 text-good" aria-hidden />
                  Ajuntament de Barcelona · pilot
                </span>
                <nav aria-label="City Insights" className="ml-4 hidden lg:block">
                  <NavLinks pathname={pathname} />
                </nav>
                <div className="ml-auto flex items-center gap-1.5">
                  <Link href="/app" className="hidden items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-xs text-fg-muted hover:bg-surface-2 hover:text-fg sm:inline-flex">
                    <ArrowLeft className="size-3.5" aria-hidden /> Rider app
                  </Link>
                  <ThemeToggle />
                  <span className="hidden text-right leading-tight xl:block">
                    <span className="block text-xs font-medium text-fg">Marta Puig</span>
                    <span className="block text-[11px] text-fg-muted">Mobility & Public Space</span>
                  </span>
                  <Avatar name="Marta Puig" size={32} />
                </div>
              </div>
              <nav aria-label="City Insights" className="scrollbar-none overflow-x-auto border-t border-line px-3 py-1.5 lg:hidden">
                <NavLinks pathname={pathname} />
              </nav>
              <div className="border-t border-line px-4 py-2 sm:px-6">
                <FilterBar />
              </div>
            </header>
            <main id="city-main" className="pb-16">
              {children}
            </main>
          </div>
        </CityFiltersProvider>
      </TooltipProvider>
    </MotionConfig>
  );
}
