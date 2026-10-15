import type { Metadata } from "next";
import { Suspense } from "react";
import { StreetMapView } from "@/components/app/street-map/street-map-view";

export const metadata: Metadata = {
  title: "Street map",
  description: "Every street UMI riders measured, scored for comfort, safety, air and noise, hour by hour.",
};

export default function StreetMapPage() {
  return (
    <Suspense>
      <StreetMapView />
    </Suspense>
  );
}
