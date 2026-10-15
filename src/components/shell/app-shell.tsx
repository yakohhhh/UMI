"use client";

import { MotionConfig } from "framer-motion";
import {
  ArrowLeft,
  Bell,
  Building2,
  ChevronsLeft,
  ChevronsRight,
  Home,
  LogOut,
  Map as MapIcon,
  Route,
  Search,
  Settings,
  Sparkles,
  User,
  Wind,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Logo } from "@/components/brand/logo";
import { Avatar } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Tooltip, TooltipProvider } from "@/components/ui/tooltip";
import { getClipStatus } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";
import { mockNow } from "@/lib/mock";
import { cn } from "@/lib/utils";
import { ClipBattery } from "./clip-battery";
import { ThemeToggle } from "./theme-toggle";

interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

export const RIDER_NAV: NavItem[] = [
  { href: "/app", label: "Home", icon: Home },
  { href: "/app/map", label: "Street map", icon: MapIcon },
  { href: "/app/routes", label: "Routes", icon: Route },
  { href: "/app/exposure", label: "Exposure", icon: Wind },
  { href: "/app/profile", label: "Profile", icon: User },
];

function isActive(pathname: string, href: string) {
  if (href === "/app") return pathname === "/app" || pathname.startsWith("/app/activities");
  return pathname === href || pathname.startsWith(`${href}/`);
}

const NOTIFICATIONS = [
  { id: 1, title: "Núria gave kudos to your Morning commute", time: "12 min ago", unread: true },
  { id: 2, title: "Cleanest window today: 18:00–19:30 on Pg. de Sant Joan", time: "1 h ago", unread: true },
  { id: 3, title: "The pothole you reported on Diagonal was confirmed by 9 riders", time: "Yesterday", unread: false },
  { id: 4, title: "Gràcia Riders: 62% of the October goal reached", time: "2 days ago", unread: false },
];

function SidebarLink({ item, collapsed, active }: { item: NavItem; collapsed: boolean; active: boolean }) {
  const link = (
    <Link
      href={item.href}
      aria-current={active ? "page" : undefined}
      className={cn(
        "group relative flex h-10 items-center gap-3 rounded-xl px-3 text-sm font-medium transition-colors",
        active ? "bg-surface-2 text-fg" : "text-fg-muted hover:bg-surface-2/60 hover:text-fg",
        collapsed && "justify-center px-0",
      )}
    >
      {active ? <span aria-hidden className="absolute top-2 bottom-2 left-0 w-[3px] rounded-r-full bg-signal" /> : null}
      <item.icon className={cn("size-[18px] shrink-0", active && "text-accent-ink")} />
      <span className={cn("truncate", collapsed && "sr-only")}>{item.label}</span>
    </Link>
  );
  return collapsed ? (
    <Tooltip content={item.label} side="right">
      {link}
    </Tooltip>
  ) : (
    link
  );
}

function Sidebar({ collapsed, onToggle, pathname }: { collapsed: boolean; onToggle: () => void; pathname: string }) {
  return (
    <aside
      className={cn(
        "sticky top-0 hidden h-dvh shrink-0 flex-col border-r border-line bg-bg-elevated transition-[width] duration-300 ease-out-expo lg:flex",
        collapsed ? "w-[76px]" : "w-60",
      )}
      aria-label="App navigation"
    >
      <div className={cn("flex h-16 items-center px-5", collapsed && "justify-center px-0")}>
        <Link href="/app" aria-label="UMI home" className="rounded-lg text-fg">
          {collapsed ? <span className="relative inline-block size-3 rounded-full bg-signal" /> : <Logo className="h-[22px]" />}
        </Link>
      </div>
      <nav className="flex-1 space-y-1 px-3 pt-2" aria-label="Rider app">
        {RIDER_NAV.map((item) => (
          <SidebarLink key={item.href} item={item} collapsed={collapsed} active={isActive(pathname, item.href)} />
        ))}
        <div className="my-4 h-px bg-line" />
        <SidebarLink item={{ href: "/city", label: "City Insights", icon: Building2 }} collapsed={collapsed} active={false} />
      </nav>
      {!collapsed ? (
        <div className="mx-3 mb-3 rounded-2xl border border-line bg-surface p-4">
          <div className="flex items-center gap-2 text-sm font-semibold text-fg">
            <Sparkles className="size-4 text-accent-ink" /> UMI Premium
          </div>
          <p className="mt-1.5 text-xs leading-5 text-fg-muted">Calmest routes and your full exposure history.</p>
          <Button asChild size="sm" variant="secondary" className="mt-3 w-full">
            <Link href="/app/profile#premium">Try 30 days free</Link>
          </Button>
        </div>
      ) : null}
      <div className={cn("border-t border-line p-3", collapsed && "flex justify-center")}>
        <Button
          variant="ghost"
          size={collapsed ? "icon" : "sm"}
          className={cn(!collapsed && "w-full justify-start")}
          onClick={onToggle}
          aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          aria-expanded={!collapsed}
        >
          {collapsed ? <ChevronsRight /> : <ChevronsLeft />}
          {!collapsed ? "Collapse" : null}
        </Button>
      </div>
    </aside>
  );
}

function ClipChip() {
  const { data } = useApi(getClipStatus);
  if (!data) return <div className="hidden h-9 w-44 animate-pulse rounded-full bg-surface-2 md:block" />;
  return (
    <>
    <Link
      href="/app/profile#clip"
      className="flex h-9 items-center gap-1.5 rounded-full border border-line bg-surface px-2.5 md:hidden"
      aria-label={`UMI Clip connected, battery ${data.battery}%`}
    >
      <span className="size-1.5 rounded-full bg-score-good" />
      <ClipBattery level={data.battery} showLabel={false} />
    </Link>
    <Link
      href="/app/profile#clip"
      className="hidden h-9 items-center gap-2.5 rounded-full border border-line bg-surface px-3 text-xs text-fg-muted transition-colors hover:border-line-strong md:flex"
      aria-label={`UMI Clip connected, battery ${data.battery}%, synced ${formatRelative(data.lastSync, mockNow())}`}
    >
      <span className="relative flex size-2">
        <span className="absolute inset-0 animate-pulse-dot rounded-full bg-score-good" />
        <span className="relative size-2 rounded-full bg-score-good" />
      </span>
      <span className="font-medium text-fg">Clip</span>
      <ClipBattery level={data.battery} />
      <span className="hidden xl:inline">Synced {formatRelative(data.lastSync, mockNow())}</span>
    </Link>
    </>
  );
}

function Topbar({ pathname }: { pathname: string }) {
  const router = useRouter();
  const searchRef = useRef<HTMLInputElement>(null);
  const [unread, setUnread] = useState(NOTIFICATIONS.filter((n) => n.unread).length);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const title = RIDER_NAV.find((n) => isActive(pathname, n.href))?.label ?? "UMI";

  return (
    <header className="sticky top-0 z-30 border-b border-line bg-bg/80 backdrop-blur-xl backdrop-saturate-150">
      <div className="flex h-16 items-center gap-3 px-4 sm:px-6">
        <Link href="/app" aria-label="UMI home" className="text-fg lg:hidden">
          <Logo className="h-5" />
        </Link>
        <span className="sr-only lg:not-sr-only lg:hidden">{title}</span>
        <form
          role="search"
          className="relative hidden max-w-md flex-1 md:block"
          onSubmit={(e) => {
            e.preventDefault();
            const q = searchRef.current?.value.trim() ?? "";
            router.push(q ? `/app/map?q=${encodeURIComponent(q)}` : "/app/map");
            searchRef.current?.blur();
          }}
        >
          <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-subtle" aria-hidden />
          <label htmlFor="app-search" className="sr-only">
            Search streets, rides and people
          </label>
          <input
            ref={searchRef}
            id="app-search"
            type="search"
            placeholder="Search streets, rides, people…"
            className="h-9 w-full rounded-xl border border-line bg-surface-2 pr-12 pl-9 text-sm text-fg placeholder:text-fg-subtle focus-visible:border-signal/50 focus-visible:ring-4 focus-visible:ring-signal/15 focus-visible:outline-none"
          />
          <kbd className="pointer-events-none absolute top-1/2 right-2.5 -translate-y-1/2 rounded-md border border-line bg-surface px-1.5 font-mono text-[10px] text-fg-subtle">⌘K</kbd>
        </form>
        <div className="ml-auto flex items-center gap-1.5 sm:gap-2">
          <ClipChip />
          <ThemeToggle />
          <DropdownMenu onOpenChange={(open) => open && setUnread(0)}>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon" aria-label={`Notifications${unread ? `, ${unread} unread` : ""}`} className="relative">
                <Bell />
                {unread ? <span aria-hidden className="absolute top-2 right-2 size-2 rounded-full bg-signal ring-2 ring-bg" /> : null}
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-80">
              <DropdownMenuLabel>Notifications</DropdownMenuLabel>
              {NOTIFICATIONS.map((n) => (
                <DropdownMenuItem key={n.id} className="items-start">
                  <span className={cn("mt-1.5 size-2 shrink-0 rounded-full", n.unread ? "bg-signal" : "bg-surface-3")} aria-hidden />
                  <span className="flex flex-col gap-0.5">
                    <span className="text-[13px] leading-5 text-fg">{n.title}</span>
                    <span className="text-xs text-fg-subtle">{n.time}</span>
                  </span>
                </DropdownMenuItem>
              ))}
            </DropdownMenuContent>
          </DropdownMenu>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button type="button" className="rounded-full" aria-label="Account menu">
                <Avatar name="Laia Serra" initials="LS" size={34} />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuLabel>Laia Serra · Free plan</DropdownMenuLabel>
              <DropdownMenuItem onSelect={() => router.push("/app/profile")}>
                <User /> Profile
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => router.push("/app/profile#clip")}>
                <Settings /> Clip settings
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => router.push("/city")}>
                <Building2 /> City Insights
              </DropdownMenuItem>
              <DropdownMenuSeparator />
              <DropdownMenuItem onSelect={() => router.push("/")}>
                <ArrowLeft /> Back to umi.city
              </DropdownMenuItem>
              <DropdownMenuItem onSelect={() => router.push("/")}>
                <LogOut /> Sign out
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>
    </header>
  );
}

function BottomNav({ pathname }: { pathname: string }) {
  return (
    <nav
      aria-label="App navigation"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-line bg-bg/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl lg:hidden"
    >
      <ul className="mx-auto grid max-w-md grid-cols-5">
        {RIDER_NAV.map((item) => {
          const active = isActive(pathname, item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn("flex h-16 flex-col items-center justify-center gap-1 text-[11px] font-medium", active ? "text-accent-ink" : "text-fg-muted")}
              >
                <item.icon className="size-5" />
                {item.label.split(" ")[0]}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

const COLLAPSE_KEY = "umi:sidebar-collapsed";
/** Pages that fill the viewport themselves (no bottom padding, no page scroll). */
const FULL_BLEED = ["/app/map", "/app/routes"];

export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem(COLLAPSE_KEY) === "1");
    } catch {}
  }, []);

  const toggle = () =>
    setCollapsed((c) => {
      try {
        localStorage.setItem(COLLAPSE_KEY, c ? "0" : "1");
      } catch {}
      return !c;
    });

  return (
    <MotionConfig reducedMotion="user">
      <TooltipProvider>
        <div className="flex min-h-dvh bg-bg text-fg">
          <a href="#app-main" className="sr-only z-50 rounded-lg bg-signal px-3 py-2 text-asphalt-900 focus:not-sr-only focus:fixed focus:top-3 focus:left-3">
            Skip to content
          </a>
          <Sidebar collapsed={collapsed} onToggle={toggle} pathname={pathname} />
          <div className="flex min-w-0 flex-1 flex-col">
            <Topbar pathname={pathname} />
            <main id="app-main" className={cn("flex-1", !FULL_BLEED.includes(pathname) && "pb-24 lg:pb-10")}>
              {children}
            </main>
          </div>
          <BottomNav pathname={pathname} />
        </div>
      </TooltipProvider>
    </MotionConfig>
  );
}

