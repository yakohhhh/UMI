import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AppShell } from "@/components/shell/app-shell";

export const metadata: Metadata = {
  title: { default: "Home", template: "%s · UMI" },
  description: "Your rides, your streets: comfort, safety, air and noise for every ride.",
};

export default function RiderLayout({ children }: { children: ReactNode }) {
  return <AppShell>{children}</AppShell>;
}
