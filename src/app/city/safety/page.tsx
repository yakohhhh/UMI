import type { Metadata } from "next";
import { SafetyView } from "@/components/city/safety-view";

export const metadata: Metadata = {
  title: "Safety",
  description: "Hard-brake hotspots at Barcelona junctions, monthly trends and the top 10 junctions to fix.",
};

export default function SafetyPage() {
  return <SafetyView />;
}
