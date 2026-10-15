"use client";

import { useTheme } from "next-themes";
import { useEffect, useState } from "react";

/** "dark" | "light", stable during SSR (dark) to avoid hydration mismatches. */
export function useResolvedTheme(): "dark" | "light" {
  const { resolvedTheme, forcedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  useEffect(() => setMounted(true), []);
  if (!mounted) return "dark";
  return (forcedTheme ?? resolvedTheme) === "light" ? "light" : "dark";
}
