import type { Metadata } from "next";
import { ApiView } from "@/components/city/api-view";

export const metadata: Metadata = {
  title: "API",
  description: "API key, quotas, endpoints and examples for the UMI City Insights open-data API, and how rider data is anonymised.",
};

export default function ApiPage() {
  return <ApiView />;
}
