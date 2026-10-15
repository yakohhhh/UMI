import type { Metadata } from "next";
import { SurfaceView } from "@/components/city/surface-view";

export const metadata: Metadata = {
  title: "Surface",
  description: "Street segments ranked by surface index, with confirmed impacts and rider counts. Exportable as CSV.",
};

export default function SurfacePage() {
  return <SurfaceView />;
}
