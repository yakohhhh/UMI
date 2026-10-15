import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex items-center gap-1.5 whitespace-nowrap rounded-full font-medium [&_svg]:size-3", {
  variants: {
    variant: {
      neutral: "bg-surface-2 text-fg-muted border border-line",
      outline: "border border-line-strong text-fg-muted",
      signal: "bg-signal/12 text-accent-ink border border-signal/25",
      lane: "bg-lane/12 text-lane-ink border border-lane/25 dark:text-lane-300",
      solid: "bg-fg text-bg",
    },
    size: {
      sm: "h-5 px-2 text-[11px]",
      md: "h-6 px-2.5 text-xs",
    },
  },
  defaultVariants: { variant: "neutral", size: "md" },
});

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, size, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ variant, size }), className)} {...props} />;
}
