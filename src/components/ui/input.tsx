import * as React from "react";
import { cn } from "@/lib/utils";

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(({ className, ...props }, ref) => (
  <input
    ref={ref}
    className={cn(
      "h-10 w-full rounded-xl border border-line bg-surface-2 px-3.5 text-sm text-fg placeholder:text-fg-subtle",
      "transition-[border-color,box-shadow] outline-none focus-visible:border-signal/60 focus-visible:ring-4 focus-visible:ring-signal/15 focus-visible:outline-none",
      className,
    )}
    {...props}
  />
));
Input.displayName = "Input";
