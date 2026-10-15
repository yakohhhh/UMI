import type { Metadata } from "next";
import type { ReactNode } from "react";
import { CityShell } from "@/components/city/city-shell";

export const metadata: Metadata = {
  title: { default: "City Insights", template: "%s · UMI City Insights" },
  description: "Street-level comfort, safety, air and noise for Barcelona, from anonymised and aggregated rides.",
};

export default function CityLayout({ children }: { children: ReactNode }) {
  return <CityShell>{children}</CityShell>;
}
