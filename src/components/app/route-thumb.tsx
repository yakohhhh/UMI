import { useId, useMemo } from "react";
import { GRID_PITCH, fitToViewport, fromGrid, pathFromPoints, toGrid } from "@/lib/geo";
import type { LngLat } from "@/lib/types";
import { cn } from "@/lib/utils";

/**
 * Static map thumbnail: the real Cerdà grid under the ride trace, drawn in SVG
 * (no map tiles, so the feed stays light).
 */
export function RouteThumb({
  coordinates,
  className,
  width = 640,
  height = 280,
  label,
  color = "var(--color-signal)",
}: {
  coordinates: LngLat[];
  className?: string;
  width?: number;
  height?: number;
  label: string;
  color?: string;
}) {
  const id = useId().replace(/:/g, "");
  const { trace, grid, start, end } = useMemo(() => {
    const fit = fitToViewport(coordinates, width, height, 0.12);
    const pts = coordinates.map((c) => fit.toSvgLngLat(c));
    // grid lines covering the viewport, in the rotated street frame
    const halfW = width / fit.scale / 2 + 300;
    const halfH = height / fit.scale / 2 + 300;
    const r = Math.hypot(halfW, halfH);
    const [cu, cv] = toGrid(coordinates[Math.floor(coordinates.length / 2)]);
    const lines: string[] = [];
    const phaseU = 46.2;
    const phaseV = -55;
    for (let k = Math.floor((cu - r - phaseU) / GRID_PITCH); k * GRID_PITCH + phaseU < cu + r; k++) {
      const u = k * GRID_PITCH + phaseU;
      lines.push(pathFromPoints([fit.toSvg(fromGrid(u, cv - r)), fit.toSvg(fromGrid(u, cv + r))]));
    }
    for (let k = Math.floor((cv - r - phaseV) / GRID_PITCH); k * GRID_PITCH + phaseV < cv + r; k++) {
      const v = k * GRID_PITCH + phaseV;
      lines.push(pathFromPoints([fit.toSvg(fromGrid(cu - r, v)), fit.toSvg(fromGrid(cu + r, v))]));
    }
    return { trace: pathFromPoints(pts), grid: lines, start: pts[0], end: pts[pts.length - 1] };
  }, [coordinates, width, height]);

  return (
    <svg viewBox={`0 0 ${width} ${height}`} className={cn("block h-auto w-full", className)} role="img" aria-label={label} preserveAspectRatio="xMidYMid slice">
      <defs>
        <radialGradient id={`rt-${id}`} cx="0.5" cy="0.5" r="0.75">
          <stop offset="0" stopColor="var(--surface-2)" />
          <stop offset="1" stopColor="var(--surface-3)" />
        </radialGradient>
      </defs>
      <rect width={width} height={height} fill={`url(#rt-${id})`} />
      <g stroke="var(--line-strong)" strokeOpacity="0.7" strokeWidth="1" fill="none">
        {grid.map((d, i) => (
          <path key={i} d={d} />
        ))}
      </g>
      <path d={trace} fill="none" stroke={color} strokeOpacity="0.25" strokeWidth="9" strokeLinecap="round" strokeLinejoin="round" />
      <path d={trace} fill="none" stroke={color} strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
      <circle cx={start[0]} cy={start[1]} r="5.5" fill="var(--surface)" stroke={color} strokeWidth="3" />
      <circle cx={end[0]} cy={end[1]} r="5.5" fill={color} stroke="var(--surface)" strokeWidth="2" />
    </svg>
  );
}
