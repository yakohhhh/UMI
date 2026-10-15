"use client";

import { Bike, Check, ChevronDown, Footprints, Layers3, MapPin, ShieldCheck } from "lucide-react";
import { usePathname } from "next/navigation";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Segmented } from "@/components/ui/segmented";
import { Tooltip } from "@/components/ui/tooltip";
import type { CityFilters, ModeFilter, Period } from "@/lib/types";
import { cn } from "@/lib/utils";

export const DISTRICTS = [
  "Ciutat Vella",
  "Eixample",
  "Sants-Montjuïc",
  "Les Corts",
  "Sarrià-Sant Gervasi",
  "Gràcia",
  "Horta-Guinardó",
  "Nou Barris",
  "Sant Andreu",
  "Sant Martí",
] as const;

const PERIODS: Period[] = ["7d", "30d", "90d", "12m"];
const MODES: ModeFilter[] = ["all", "bike", "run"];

export const PERIOD_LABEL: Record<Period, string> = { "7d": "last 7 days", "30d": "last 30 days", "90d": "last 90 days", "12m": "last 12 months" };

interface Ctx {
  filters: CityFilters;
  setPeriod: (p: Period) => void;
  setMode: (m: ModeFilter) => void;
  setDistricts: (d: string[]) => void;
  toggleDistrict: (d: string) => void;
}

const FiltersContext = createContext<Ctx | null>(null);

function readUrl(): CityFilters {
  const def: CityFilters = { period: "30d", districts: [], mode: "all" };
  const q = new URLSearchParams(window.location.search);
  const period = q.get("period") as Period | null;
  const mode = q.get("mode") as ModeFilter | null;
  const districts = (q.get("districts") ?? "")
    .split(",")
    .map((d) => d.trim())
    .filter((d) => (DISTRICTS as readonly string[]).includes(d));
  return {
    period: period && PERIODS.includes(period) ? period : def.period,
    mode: mode && MODES.includes(mode) ? mode : def.mode,
    districts,
  };
}

/**
 * Filters shared by every City Insights page. They live in the layout, so they
 * survive navigation, and are mirrored in the URL so a view can be shared.
 */
const DEFAULT_FILTERS: CityFilters = { period: "30d", districts: [], mode: "all" };

export function CityFiltersProvider({ children }: { children: ReactNode }) {
  // Server and first client render use the defaults (no hydration mismatch); the URL is read right after.
  const [filters, setFilters] = useState<CityFilters>(DEFAULT_FILTERS);
  const pathname = usePathname();

  useEffect(() => setFilters(readUrl()), []);

  useEffect(() => {
    if (filters === DEFAULT_FILTERS) return;
    const q = new URLSearchParams(window.location.search);
    const set = (k: string, v: string, def: string) => (v === def ? q.delete(k) : q.set(k, v));
    set("period", filters.period, "30d");
    set("mode", filters.mode, "all");
    set("districts", filters.districts.join(","), "");
    const qs = q.toString();
    const next = `${window.location.pathname}${qs ? `?${qs}` : ""}${window.location.hash}`;
    if (next !== `${window.location.pathname}${window.location.search}${window.location.hash}`) window.history.replaceState(window.history.state, "", next);
  }, [filters, pathname]);

  const setPeriod = useCallback((period: Period) => setFilters((f) => ({ ...f, period })), []);
  const setMode = useCallback((mode: ModeFilter) => setFilters((f) => ({ ...f, mode })), []);
  const setDistricts = useCallback((districts: string[]) => setFilters((f) => ({ ...f, districts })), []);
  const toggleDistrict = useCallback(
    (d: string) => setFilters((f) => ({ ...f, districts: f.districts.includes(d) ? f.districts.filter((x) => x !== d) : [...f.districts, d] })),
    [],
  );

  const value = useMemo(() => ({ filters, setPeriod, setMode, setDistricts, toggleDistrict }), [filters, setPeriod, setMode, setDistricts, toggleDistrict]);
  return <FiltersContext.Provider value={value}>{children}</FiltersContext.Provider>;
}

export function useCityFilters() {
  const ctx = useContext(FiltersContext);
  if (!ctx) throw new Error("useCityFilters must be used inside <CityFiltersProvider>");
  return ctx;
}

function DistrictPicker() {
  const { filters, toggleDistrict, setDistricts } = useCityFilters();
  const n = filters.districts.length;
  const label = n === 0 ? "All districts" : n === 1 ? filters.districts[0] : `${n} districts`;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button variant="secondary" size="sm" className={cn("max-w-[220px]", n > 0 && "border-signal/40")} aria-label={`District filter: ${label}`}>
          <MapPin className={cn(n > 0 && "text-accent-ink")} />
          <span className="truncate">{label}</span>
          <ChevronDown className="opacity-60" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-72 p-2" align="start">
        <div className="flex items-center justify-between px-2 pt-1 pb-2">
          <span className="label-mono text-[10px] text-fg-subtle">Districts</span>
          <button type="button" onClick={() => setDistricts([])} className="text-xs text-accent-ink hover:underline disabled:opacity-40" disabled={n === 0}>
            Clear
          </button>
        </div>
        <ul className="max-h-80 space-y-0.5 overflow-y-auto" role="group" aria-label="Districts">
          {DISTRICTS.map((d) => {
            const on = filters.districts.includes(d);
            return (
              <li key={d}>
                <button
                  type="button"
                  role="checkbox"
                  aria-checked={on}
                  onClick={() => toggleDistrict(d)}
                  className="flex w-full items-center gap-2.5 rounded-lg px-2 py-1.5 text-left text-sm text-fg hover:bg-surface-2"
                >
                  <span className={cn("flex size-4 items-center justify-center rounded border", on ? "border-signal bg-signal text-asphalt-900" : "border-line-strong")} aria-hidden>
                    {on ? <Check className="size-3" strokeWidth={3} /> : null}
                  </span>
                  {d}
                </button>
              </li>
            );
          })}
        </ul>
      </PopoverContent>
    </Popover>
  );
}

export function AnonymisedBadge({ className }: { className?: string }) {
  return (
    <Tooltip content="Every figure aggregates at least 5 riders per street and hour. The first and last 200 m of each trip are removed on the rider's phone, before upload." side="bottom">
      <span
        tabIndex={0}
        className={cn(
          "inline-flex h-8 items-center gap-1.5 rounded-full border border-good-fill/30 bg-good-fill/10 px-3 text-xs font-medium whitespace-nowrap text-good focus-visible:ring-2 focus-visible:ring-good-fill/40 focus-visible:outline-none",
          className,
        )}
      >
        <ShieldCheck className="size-3.5" aria-hidden />
        Anonymised & aggregated <span className="hidden text-good/80 xl:inline">— trip start/end trimmed</span>
      </span>
    </Tooltip>
  );
}

export function FilterBar() {
  const { filters, setPeriod, setMode } = useCityFilters();
  return (
    <div className="flex flex-wrap items-center gap-2" role="group" aria-label="Filters">
      <Segmented
        size="sm"
        value={filters.period}
        onChange={setPeriod}
        label="Period"
        options={PERIODS.map((p) => ({ value: p, label: p.replace("d", " d").replace("m", " mo") }))}
      />
      <DistrictPicker />
      <Segmented
        size="sm"
        value={filters.mode}
        onChange={setMode}
        label="Activity type"
        options={[
          { value: "all", label: "All", icon: <Layers3 /> },
          { value: "bike", label: "Bike", icon: <Bike /> },
          { value: "run", label: "Run", icon: <Footprints /> },
        ]}
      />
      <AnonymisedBadge className="ml-auto" />
    </div>
  );
}
