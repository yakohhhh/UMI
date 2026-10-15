import type { StyleSpecification } from "maplibre-gl";

/**
 * Basemap selection.
 * - No token: free CARTO GL styles (Dark Matter / Positron) rendered by MapLibre.
 * - NEXT_PUBLIC_MAPBOX_TOKEN set: Mapbox dark-v11 / light-v11, with mapbox:// URLs
 *   rewritten for MapLibre by `transformRequest`.
 */
export const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";

export type MapTheme = "dark" | "light";

export function basemapStyle(theme: MapTheme): string {
  if (MAPBOX_TOKEN) return `mapbox://styles/mapbox/${theme === "dark" ? "dark-v11" : "light-v11"}`;
  return theme === "dark"
    ? "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
    : "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";
}

/** Rewrites mapbox:// style, sprite, glyph and tileset URLs to the Mapbox HTTP API. */
export function transformRequest(url: string) {
  if (!MAPBOX_TOKEN || !url.startsWith("mapbox://")) return { url };
  const token = `access_token=${MAPBOX_TOKEN}`;
  const path = url.slice("mapbox://".length);
  if (path.startsWith("styles/")) {
    return { url: `https://api.mapbox.com/styles/v1/${path.slice("styles/".length)}?${token}` };
  }
  if (path.startsWith("sprites/")) {
    // mapbox://sprites/{user}/{style}[@2x].{json|png}
    const m = path.match(/^sprites\/([^/]+)\/([^/@.]+)(@2x)?\.(json|png)$/);
    if (m) return { url: `https://api.mapbox.com/styles/v1/${m[1]}/${m[2]}/sprite${m[3] ?? ""}.${m[4]}?${token}` };
  }
  if (path.startsWith("fonts/")) {
    return { url: `https://api.mapbox.com/fonts/v1/${path.slice("fonts/".length)}?${token}` };
  }
  // tileset ids, e.g. mapbox://mapbox.mapbox-streets-v8,mapbox.mapbox-terrain-v2
  return { url: `https://api.mapbox.com/v4/${path}.json?secure&${token}` };
}

/** Minimal offline style used when the remote basemap can't be reached. */
export function fallbackStyle(theme: MapTheme): StyleSpecification {
  return {
    version: 8,
    name: "umi-fallback",
    sources: {},
    layers: [{ id: "background", type: "background", paint: { "background-color": theme === "dark" ? "#070b14" : "#dfe5ea" } }],
  };
}

export const BASE_COLORS: Record<MapTheme, { land: string; landLine: string; district: string; casing: string; muted: string }> = {
  dark: { land: "#0e1626", landLine: "#26344f", district: "#3a4a66", casing: "#05080e", muted: "#5b6b86" },
  light: { land: "#f3f1ec", landLine: "#cfc8b9", district: "#b9b2a4", casing: "#ffffff", muted: "#8794ab" },
};
