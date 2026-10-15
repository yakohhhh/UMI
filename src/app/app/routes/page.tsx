import type { Metadata } from "next";
import { Suspense } from "react";
import { RoutePlanner } from "@/components/app/routes/route-planner";

export const metadata: Metadata = {
  title: "Routes",
  description: "Compare the fastest, calmest and cleanest way across Barcelona, forecast for your departure time.",
};

export default function RoutesPage() {
  return (
    <Suspense>
      <RoutePlanner />
    </Suspense>
  );
}
