"use client";

import "maplibre-gl/dist/maplibre-gl.css";
import { forwardRef, useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import MapGL, { Layer, NavigationControl, Source, type MapProps, type MapRef } from "react-map-gl/maplibre";
import { getCityOutline, getDistrictsGeo } from "@/lib/api";
import { BARCELONA_CENTER } from "@/lib/geo";
import { useResolvedTheme } from "@/lib/hooks/use-resolved-theme";
import type { GeoFeatureCollection } from "@/lib/types";
import { cn } from "@/lib/utils";
import { BASE_COLORS, basemapStyle, fallbackStyle, transformRequest, type MapTheme } from "./map-style";

export interface BaseMapProps extends Omit<MapProps, "mapStyle" | "children"> {
  children?: ReactNode;
  className?: string;
  /** Accessible description of what the map shows. */
  label: string;
  showControls?: boolean;
  /** Called with the resolved theme so data layers can adapt their colours. */
  onThemeChange?: (theme: MapTheme) => void;
}

/**
 * MapLibre map with the UMI basemap. Falls back to a self-contained style
 * (city outline + districts) if the remote basemap can't be loaded, so demos
 * work offline or behind strict networks.
 */
export const BaseMap = forwardRef<MapRef, BaseMapProps>(function BaseMap(
  { children, className, label, showControls = true, initialViewState, onError, onLoad, ...props },
  ref,
) {
  const theme = useResolvedTheme();
  const [fallback, setFallback] = useState(false);
  const [base, setBase] = useState<{ city: GeoFeatureCollection; districts: GeoFeatureCollection } | null>(null);
  const loaded = useRef(false);

  useEffect(() => {
    // If the remote style hasn't loaded after a few seconds, switch to the local one.
    const t = window.setTimeout(() => {
      if (!loaded.current) setFallback(true);
    }, 6000);
    return () => window.clearTimeout(t);
  }, []);

  useEffect(() => {
    if (!fallback || base) return;
    Promise.all([getCityOutline(), getDistrictsGeo()]).then(([city, districts]) => setBase({ city, districts }));
  }, [fallback, base]);

  const handleError = useCallback<NonNullable<MapProps["onError"]>>(
    (e) => {
      const msg = String((e as { error?: Error }).error?.message ?? "");
      if (!loaded.current || /style|Failed to fetch|AJAXError|NetworkError|403|401/i.test(msg)) setFallback(true);
      onError?.(e);
    },
    [onError],
  );

  const colors = BASE_COLORS[theme];

  return (
    <div className={cn("relative overflow-hidden bg-[var(--map-bg)]", className)} role="region" aria-label={label}>
      <MapGL
        ref={ref}
        initialViewState={initialViewState ?? { longitude: BARCELONA_CENTER[0], latitude: BARCELONA_CENTER[1], zoom: 13 }}
        mapStyle={fallback ? fallbackStyle(theme) : basemapStyle(theme)}
        transformRequest={transformRequest}
        attributionControl={{ compact: true }}
        style={{ width: "100%", height: "100%" }}
        dragRotate={false}
        pitchWithRotate={false}
        maxPitch={0}
        onError={handleError}
        onLoad={(e) => {
          loaded.current = true;
          onLoad?.(e);
        }}
        {...props}
      >
        {fallback && base ? (
          <>
            <Source id="umi-base-city" type="geojson" data={base.city}>
              <Layer id="umi-base-land" type="fill" paint={{ "fill-color": colors.land }} />
              <Layer id="umi-base-coast" type="line" paint={{ "line-color": colors.landLine, "line-width": 1 }} />
            </Source>
            <Source id="umi-base-districts" type="geojson" data={base.districts}>
              <Layer id="umi-base-district-lines" type="line" paint={{ "line-color": colors.district, "line-width": 0.8, "line-dasharray": [3, 2] }} />
            </Source>
          </>
        ) : null}
        {/* data layers mount after the fallback base so they draw on top of it */}
        {!fallback || base ? <MapChildren key={fallback ? "fallback" : "remote"}>{children}</MapChildren> : null}
        {showControls ? <NavigationControl position="top-right" showCompass={false} /> : null}
      </MapGL>
    </div>
  );
});

function MapChildren({ children }: { children: ReactNode }) {
  return <>{children}</>;
}

export type { MapRef };
