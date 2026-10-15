import type { Metadata } from "next";
import { OverviewView } from "@/components/city/overview-view";

export const metadata: Metadata = { title: { absolute: "City Insights · UMI" } };

export default function CityOverviewPage() {
  return <OverviewView />;
}
