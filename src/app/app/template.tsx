"use client";

import { motion } from "framer-motion";
import type { ReactNode } from "react";

/** Page transition: soft fade with a short upward slide. */
export default function RiderTemplate({ children }: { children: ReactNode }) {
  return (
    <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}>
      {children}
    </motion.div>
  );
}
