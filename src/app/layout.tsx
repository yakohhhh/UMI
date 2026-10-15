import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { Providers } from "@/components/providers";
import { grotesk, plex, plexMono } from "./fonts";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL ?? "http://localhost:3000"),
  title: {
    default: "UMI — Know the street before you take it.",
    template: "%s · UMI",
  },
  description:
    "UMI Clip measures every street you ride or run — comfort, safety, air and noise — and turns Barcelona's streets into calmer, cleaner routes.",
  applicationName: "UMI",
  openGraph: {
    title: "UMI — Know the street before you take it.",
    description: "A clip-on sensor that scores every street for comfort, safety, air and noise. Launching in Barcelona.",
    siteName: "UMI",
    locale: "en_GB",
    type: "website",
  },
  twitter: { card: "summary_large_image" },
};

export const viewport: Viewport = {
  themeColor: "#0b1220",
  colorScheme: "dark light",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning className={`${grotesk.variable} ${plex.variable} ${plexMono.variable}`}>
      <body>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
