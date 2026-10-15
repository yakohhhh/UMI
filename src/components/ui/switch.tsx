"use client";

import * as SwitchPrimitive from "@radix-ui/react-switch";
import * as React from "react";
import { cn } from "@/lib/utils";

export const Switch = React.forwardRef<React.ElementRef<typeof SwitchPrimitive.Root>, React.ComponentPropsWithoutRef<typeof SwitchPrimitive.Root>>(
  ({ className, ...props }, ref) => (
    <SwitchPrimitive.Root
      ref={ref}
      className={cn(
        "peer inline-flex h-6 w-10 shrink-0 items-center rounded-full border border-line bg-surface-3 p-0.5 transition-colors",
        "data-[state=checked]:border-signal/40 data-[state=checked]:bg-signal disabled:cursor-not-allowed disabled:opacity-50",
        className,
      )}
      {...props}
    >
      <SwitchPrimitive.Thumb className="pointer-events-none block size-[18px] rounded-full bg-white shadow-[0_1px_3px_rgb(0_0_0/0.3)] transition-transform duration-200 ease-out-cubic data-[state=checked]:translate-x-4" />
    </SwitchPrimitive.Root>
  ),
);
Switch.displayName = "Switch";
