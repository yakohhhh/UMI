import type { LngLat } from "./types";

/** Local equirectangular projection centred on Barcelona (metres). */
const LAT0 = 41.39;
const LON0 = 2.17;
const KX = Math.cos((LAT0 * Math.PI) / 180) * 111320;
const KY = 110574;

/** Cerdà grid orientation (fitted on census boundaries) and pitch. */
const BEARING = (45.11 * Math.PI) / 180;
const E1: [number, number] = [Math.sin(BEARING), Math.cos(BEARING)];
const E2: [number, number] = [Math.sin(BEARING + Math.PI / 2), Math.cos(BEARING + Math.PI / 2)];
export const GRID_PITCH = 133.4;

export const BARCELONA_CENTER: LngLat = [2.1686, 41.3954];

export function project([lng, lat]: LngLat): [number, number] {
  return [(lng - LON0) * KX, (lat - LAT0) * KY];
}

export function unproject([x, y]: [number, number]): LngLat {
  return [LON0 + x / KX, LAT0 + y / KY];
}

export function toGrid(ll: LngLat): [number, number] {
  const [x, y] = project(ll);
  return [x * E1[0] + y * E1[1], x * E2[0] + y * E2[1]];
}

export function fromGrid(u: number, v: number): [number, number] {
  return [u * E1[0] + v * E2[0], u * E1[1] + v * E2[1]];
}

export function distance(a: LngLat, b: LngLat) {
  const [x1, y1] = project(a);
  const [x2, y2] = project(b);
  return Math.hypot(x2 - x1, y2 - y1);
}

/** Shortest distance (m) from a point to a polyline. */
export function distanceToLine(p: LngLat, line: LngLat[]) {
  const [px, py] = project(p);
  let best = Infinity;
  for (let i = 1; i < line.length; i++) {
    const [ax, ay] = project(line[i - 1]);
    const [bx, by] = project(line[i]);
    const dx = bx - ax;
    const dy = by - ay;
    const len2 = dx * dx + dy * dy;
    const t = len2 ? Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / len2)) : 0;
    best = Math.min(best, Math.hypot(px - (ax + t * dx), py - (ay + t * dy)));
  }
  return best;
}

export function bbox(coords: LngLat[]): [number, number, number, number] {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const [x, y] of coords) {
    if (x < minX) minX = x;
    if (y < minY) minY = y;
    if (x > maxX) maxX = x;
    if (y > maxY) maxY = y;
  }
  return [minX, minY, maxX, maxY];
}

/**
 * Fits coordinates into a width × height viewport (with padding) and returns
 * a projector to SVG space plus the metres-per-pixel scale.
 */
export function fitToViewport(coords: LngLat[], width: number, height: number, padding = 0.14) {
  const pts = coords.map(project);
  const xs = pts.map((p) => p[0]);
  const ys = pts.map((p) => p[1]);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  const spanX = Math.max(maxX - minX, 300);
  const spanY = Math.max(maxY - minY, 300);
  const scale = Math.min((width * (1 - padding * 2)) / spanX, (height * (1 - padding * 2)) / spanY);
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  const toSvg = ([x, y]: [number, number]): [number, number] => [width / 2 + (x - cx) * scale, height / 2 - (y - cy) * scale];
  return { toSvg, scale, cx, cy, toSvgLngLat: (ll: LngLat) => toSvg(project(ll)) };
}

export function pathFromPoints(points: [number, number][]) {
  return points.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(1)} ${y.toFixed(1)}`).join("");
}

/** Interpolated point at a fraction (0–1) of a polyline's length. */
export function pointAlong(coords: LngLat[], t: number): LngLat {
  if (coords.length < 2) return coords[0];
  const seg: number[] = [];
  let total = 0;
  for (let i = 1; i < coords.length; i++) {
    const d = distance(coords[i - 1], coords[i]);
    seg.push(d);
    total += d;
  }
  let target = total * Math.max(0, Math.min(1, t));
  for (let i = 0; i < seg.length; i++) {
    if (target <= seg[i]) {
      const k = seg[i] ? target / seg[i] : 0;
      return [coords[i][0] + (coords[i + 1][0] - coords[i][0]) * k, coords[i][1] + (coords[i + 1][1] - coords[i][1]) * k];
    }
    target -= seg[i];
  }
  return coords[coords.length - 1];
}

/** LngLat bounds with padding, ready for map.fitBounds. */
export function boundsOf(coords: LngLat[]): [[number, number], [number, number]] {
  const [a, b, c, d] = bbox(coords);
  return [
    [a, b],
    [c, d],
  ];
}
