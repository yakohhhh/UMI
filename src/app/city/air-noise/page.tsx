import type { Metadata } from "next";
import { AirNoiseView } from "@/components/city/air-noise-view";

export const metadata: Metadata = {
  title: "Air & noise",
  description: "PM2.5 and noise measured on Barcelona streets by hour and weekday, against the EU 2030 limit and WHO guidelines.",
};

export default function AirNoisePage() {
  return <AirNoiseView />;
}
