import type { Metadata } from "next";
import { ExposureView } from "@/components/app/exposure/exposure-view";

export const metadata: Metadata = {
  title: "Exposure",
  description: "Your PM2.5 and noise exposure while riding, week by week, against the WHO guidelines and the EU 2030 limit.",
};

export default function ExposurePage() {
  return <ExposureView />;
}
