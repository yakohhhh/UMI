"use client";

import { ArrowDown, ArrowUp, ArrowUpDown, Bike, Download, Search } from "lucide-react";
import dynamic from "next/dynamic";
import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Delta } from "@/components/data/delta";
import { EmptyState, ErrorState } from "@/components/data/states";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Segmented } from "@/components/ui/segmented";
import { Skeleton } from "@/components/ui/skeleton";
import { getStreetSegments, getSurfaceRanking } from "@/lib/api";
import { downloadFile, toCsv } from "@/lib/download";
import { formatInt, shortStreet } from "@/lib/format";
import { useApi } from "@/lib/hooks/use-api";
import { mockNow } from "@/lib/mock";
import { BAND_VAR, DIMENSIONS, scoreBand } from "@/lib/score";
import { searchable } from "@/lib/street-geojson";
import type { SurfaceRankRow } from "@/lib/types";
import { cn } from "@/lib/utils";
import { PERIOD_LABEL, useCityFilters } from "./city-filters";
import { PageHeader } from "./page-header";
import type { MapSegment } from "./segments-map";

const SegmentsMap = dynamic(() => import("./segments-map"), { ssr: false, loading: () => <Skeleton className="size-full rounded-none" /> });

type SortKey = "surfaceIndex" | "confirmedImpacts" | "riders30d" | "trend" | "lengthM" | "street";
const PAGE = 20;

const COLUMNS: { key: SortKey; label: string; numeric: boolean; className?: string }[] = [
  { key: "street", label: "Street segment", numeric: false },
  { key: "surfaceIndex", label: "Surface index", numeric: true },
  { key: "confirmedImpacts", label: "Impacts", numeric: true, className: "hidden md:table-cell" },
  { key: "riders30d", label: "Riders", numeric: true, className: "hidden sm:table-cell" },
  { key: "trend", label: "Trend", numeric: true, className: "hidden lg:table-cell" },
  { key: "lengthM", label: "Length", numeric: true, className: "hidden 2xl:table-cell" },
];

export function SurfaceView() {
  const { filters, setMode } = useCityFilters();
  const ranking = useApi(() => getSurfaceRanking(filters), [filters.period, filters.mode, filters.districts.join(",")]);
  const streets = useApi(getStreetSegments);
  const [sort, setSort] = useState<{ key: SortKey; dir: 1 | -1 }>({ key: "surfaceIndex", dir: 1 });
  const [band, setBand] = useState<"all" | "bad" | "mid">("all");
  const [query, setQuery] = useState("");
  const [shown, setShown] = useState(PAGE);
  const [active, setActive] = useState<string | null>(null);

  const rows = useMemo(() => {
    const q = searchable(query.trim());
    const list = (ranking.data ?? []).filter(
      (r) =>
        (band === "all" || scoreBand(r.surfaceIndex) === band) &&
        (!q || searchable(`${r.street} ${r.from ?? ""} ${r.to ?? ""} ${r.district}`).includes(q)),
    );
    const { key, dir } = sort;
    return list.sort((a, b) => (key === "street" ? a.street.localeCompare(b.street) * dir : ((a[key] as number) - (b[key] as number)) * dir));
  }, [ranking.data, sort, band, query]);

  const mapSegments = useMemo((): MapSegment[] => {
    if (!streets.data) return [];
    const geom = new Map(streets.data.map((s) => [s.id, s.coordinates]));
    return rows.flatMap((r) => {
      const c = geom.get(r.segmentId);
      return c ? [{ id: r.segmentId, coordinates: c, value: r.surfaceIndex, label: r.street }] : [];
    });
  }, [rows, streets.data]);

  const exportCsv = () => {
    const columns = ["segment_id", "street", "from", "to", "district", "surface_index", "confirmed_impacts", "riders", "trend_pts", "length_m"];
    const csv = toCsv(
      rows.map((r: SurfaceRankRow) => ({
        segment_id: r.segmentId,
        street: r.street,
        from: r.from,
        to: r.to,
        district: r.district,
        surface_index: r.surfaceIndex,
        confirmed_impacts: r.confirmedImpacts,
        riders: r.riders30d,
        trend_pts: r.trend,
        length_m: r.lengthM,
      })),
      columns,
    );
    downloadFile(`umi-surface-ranking-${filters.period}-${mockNow().toISOString().slice(0, 10)}.csv`, csv, "text/csv;charset=utf-8");
  };

  const toggleSort = (key: SortKey) => setSort((s) => (s.key === key ? { key, dir: s.dir === 1 ? -1 : 1 } : { key, dir: key === "street" || key === "surfaceIndex" ? 1 : -1 }));

  // Clicking a segment on the map reveals its row.
  const [picked, setPicked] = useState<string | null>(null);
  const pick = (id: string) => {
    const i = rows.findIndex((r) => r.segmentId === id);
    if (i < 0) return;
    if (i >= shown) setShown(Math.ceil((i + 1) / PAGE) * PAGE);
    setActive(id);
    setPicked(id);
  };
  useEffect(() => {
    if (!picked) return;
    const el = document.getElementById(`row-${picked}`);
    el?.scrollIntoView({ block: "center", behavior: "smooth" });
    el?.focus({ preventScroll: true });
    setPicked(null);
  }, [picked, shown]);

  let body: ReactNode;
  if (ranking.error) body = <ErrorState error={ranking.error} onRetry={ranking.retry} />;
  else if (!ranking.data)
    body = (
      <div className="space-y-2 p-4" aria-busy="true" aria-label="Loading the surface ranking">
        {Array.from({ length: 10 }, (_, i) => (
          <Skeleton key={i} className="h-11" />
        ))}
      </div>
    );
  else if (filters.mode === "run")
    body = (
      <EmptyState
        className="m-4"
        icon={<Bike />}
        title="Runners don't measure the surface"
        body="Surface vibration is only recorded on bikes, where the Clip is mounted on the handlebar. Switch to Bike or All to see the ranking."
        action={
          <Button size="sm" onClick={() => setMode("bike")}>
            Show bike data
          </Button>
        }
      />
    );
  else if (rows.length === 0)
    body = (
      <EmptyState
        className="m-4"
        title={ranking.data.length ? "No segment matches" : "No surface data for this selection"}
        body={ranking.data.length ? "Try another street name or remove the band filter." : "Fewer than 5 riders crossed these streets in the period."}
      />
    );
  else
    body = (
      <>
        <div className="relative overflow-x-auto">
          <table className="w-full text-left text-[13px]">
            <caption className="sr-only">
              Street segments ranked by surface index, {PERIOD_LABEL[filters.period]}. Sorted by {sort.key} {sort.dir === 1 ? "ascending" : "descending"}.
            </caption>
            <thead className="sticky top-0 z-10 bg-surface">
              <tr className="border-b border-line">
                <th scope="col" className="w-10 py-2.5 pl-4 font-mono text-[10px] font-normal text-fg-subtle">
                  #
                </th>
                {COLUMNS.map((c) => {
                  const on = sort.key === c.key;
                  const Icon = !on ? ArrowUpDown : sort.dir === 1 ? ArrowUp : ArrowDown;
                  return (
                    <th
                      key={c.key}
                      scope="col"
                      aria-sort={on ? (sort.dir === 1 ? "ascending" : "descending") : "none"}
                      className={cn("px-3 py-1.5 font-normal", c.numeric && "text-right", c.className)}
                    >
                      <button
                        type="button"
                        onClick={() => toggleSort(c.key)}
                        className={cn("label-mono inline-flex items-center gap-1 rounded px-1 py-1 text-[10px] hover:text-fg", on ? "text-fg" : "text-fg-subtle")}
                      >
                        {c.label}
                        <Icon className="size-3" aria-hidden />
                      </button>
                    </th>
                  );
                })}
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, shown).map((r, i) => {
                const b = scoreBand(r.surfaceIndex);
                return (
                  <tr
                    key={r.segmentId}
                    id={`row-${r.segmentId}`}
                    onMouseEnter={() => setActive(r.segmentId)}
                    onMouseLeave={() => setActive(null)}
                    onFocus={() => setActive(r.segmentId)}
                    tabIndex={0}
                    aria-label={`${r.street}${r.from ? ` from ${r.from}` : ""}${r.to ? ` to ${r.to}` : ""}, ${r.district}: surface index ${r.surfaceIndex}, ${DIMENSIONS.comfort.bands[b]}`}
                    className={cn("border-b border-line outline-none transition-colors focus-visible:bg-surface-2 focus-visible:shadow-[inset_0_0_0_2px_var(--color-signal)]", active === r.segmentId ? "bg-surface-2" : "hover:bg-surface-2/60")}
                  >
                    <td className="py-2.5 pl-4 font-mono text-[11px] text-fg-subtle">{i + 1}</td>
                    <td className="max-w-[280px] px-3 py-2.5">
                      <p className="truncate font-medium text-fg">{shortStreet(r.street)}</p>
                      <p className="truncate text-xs text-fg-muted">
                        {[r.from, r.to].filter(Boolean).join(" → ") || "Whole segment"} · {r.district}
                      </p>
                    </td>
                    <td className="px-3 py-2.5">
                      <div className="flex items-center justify-end gap-2.5">
                        <div className="hidden h-1.5 w-20 overflow-hidden rounded-full bg-surface-3 sm:block" aria-hidden>
                          <div className="h-full rounded-full" style={{ width: `${r.surfaceIndex}%`, background: BAND_VAR[b].fill }} />
                        </div>
                        <span className="w-7 text-right font-num font-semibold" style={{ color: BAND_VAR[b].ink }}>
                          {r.surfaceIndex}
                        </span>
                      </div>
                    </td>
                    <td className="hidden px-3 py-2.5 text-right font-num md:table-cell">{r.confirmedImpacts}</td>
                    <td className="hidden px-3 py-2.5 text-right font-num sm:table-cell">{formatInt(r.riders30d)}</td>
                    <td className="hidden px-3 py-2.5 text-right lg:table-cell">
                      <Delta value={r.trend} unit="" suffix="" />
                    </td>
                    <td className="hidden px-3 py-2.5 text-right font-num text-fg-muted 2xl:table-cell">{r.lengthM} m</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 text-xs text-fg-muted">
          <span>
            Showing <span className="font-num text-fg">{Math.min(shown, rows.length)}</span> of <span className="font-num text-fg">{rows.length}</span> segments
          </span>
          {shown < rows.length ? (
            <Button variant="secondary" size="sm" onClick={() => setShown((n) => n + PAGE)}>
              Show {Math.min(PAGE, rows.length - shown)} more
            </Button>
          ) : null}
        </div>
      </>
    );

  return (
    <div className="mx-auto max-w-[1480px] space-y-5 px-4 py-5 sm:px-6">
      <PageHeader
        eyebrow={`Surface · ${PERIOD_LABEL[filters.period]}`}
        title="Where the asphalt hurts"
        description="Every segment riders crossed, ranked by surface index: the vibration their Clips measured, 100 being glass-smooth. Impacts are potholes confirmed by at least 3 riders."
      >
        <Button variant="secondary" size="sm" onClick={exportCsv} disabled={!rows.length}>
          <Download /> Export CSV
        </Button>
      </PageHeader>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_520px]">
        <Card className="min-w-0 overflow-hidden">
          <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
            <div className="relative min-w-[200px] flex-1">
              <Search className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-fg-subtle" aria-hidden />
              <label htmlFor="surface-search" className="sr-only">
                Filter by street or district
              </label>
              <input
                id="surface-search"
                type="search"
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value);
                  setShown(PAGE);
                }}
                placeholder="Filter by street or district…"
                className="h-9 w-full rounded-xl border border-line bg-surface-2 pr-3 pl-9 text-sm text-fg placeholder:text-fg-subtle focus-visible:border-signal/50 focus-visible:ring-4 focus-visible:ring-signal/15 focus-visible:outline-none"
              />
            </div>
            <Segmented
              size="sm"
              value={band}
              onChange={(v) => {
                setBand(v);
                setShown(PAGE);
              }}
              label="Surface band"
              options={[
                { value: "all", label: "All" },
                { value: "bad", label: "Rough < 45" },
                { value: "mid", label: "Bumpy 45–69" },
              ]}
            />
          </div>
          {body}
        </Card>

        <Card className="h-[420px] overflow-hidden xl:sticky xl:top-[140px] xl:h-[calc(100dvh-170px)]">
          {mapSegments.length || streets.loading ? (
            <SegmentsMap
              segments={mapSegments}
              activeId={active}
              onHover={setActive}
              onPick={pick}
              label={`Map of ${mapSegments.length} street segments coloured by surface index. Hover a row to locate it.`}
            />
          ) : (
            <div className="flex size-full items-center justify-center bg-[var(--map-bg)] text-sm text-fg-muted">Nothing to map for this selection</div>
          )}
        </Card>
      </div>
    </div>
  );
}
