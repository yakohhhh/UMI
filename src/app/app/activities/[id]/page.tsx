import type { Metadata } from "next";
import { RideReport } from "@/components/app/ride-report";

export const metadata: Metadata = { title: "Ride report" };

export default function ActivityPage() {
  return <RideReport />;
}
