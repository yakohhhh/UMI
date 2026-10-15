"use client";

import * as SliderPrimitive from "@radix-ui/react-slider";
import * as React from "react";
import { cn } from "@/lib/utils";

export const Slider = React.forwardRef<
  React.ElementRef<typeof SliderPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof SliderPrimitive.Root> & { thumbLabel: string; trackClassName?: string }
>(({ className, thumbLabel, trackClassName, ...props }, ref) => (
  <SliderPrimitive.Root ref={ref} className={cn("relative flex h-6 w-full touch-none items-center select-none", className)} {...props}>
    <SliderPrimitive.Track className={cn("relative h-1.5 grow overflow-hidden rounded-full bg-surface-3", trackClassName)}>
      <SliderPrimitive.Range className="absolute h-full rounded-full bg-signal" />
    </SliderPrimitive.Track>
    <SliderPrimitive.Thumb
      aria-label={thumbLabel}
      className="block size-5 rounded-full border-2 border-signal bg-white shadow-[0_2px_8px_rgb(0_0_0/0.25)] transition-transform hover:scale-110 focus-visible:ring-4 focus-visible:ring-signal/25 focus-visible:outline-none"
    />
  </SliderPrimitive.Root>
));
Slider.displayName = "Slider";
