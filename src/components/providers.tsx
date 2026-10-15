"use client";

import { ThemeProvider } from "next-themes";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

/**
 * App-wide providers. The marketing landing is always dark; the rider app and
 * City Insights follow the user's light/dark choice (dark by default).
 */
export function Providers({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const forcedTheme = pathname === "/" ? "dark" : undefined;

  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="dark"
      enableSystem={false}
      forcedTheme={forcedTheme}
      disableTransitionOnChange
    >
      {children}
    </ThemeProvider>
  );
}
