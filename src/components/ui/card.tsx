import * as React from "react";
import { cn } from "@/lib/utils";

export const Card = React.forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement> & { interactive?: boolean }>(
  ({ className, interactive, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        "rounded-2xl border border-line bg-surface text-fg shadow-[var(--shadow-soft)]",
        interactive && "transition-[border-color,transform,box-shadow] duration-300 hover:-translate-y-0.5 hover:border-line-strong hover:shadow-[var(--shadow-lift)]",
        className,
      )}
      {...props}
    />
  ),
);
Card.displayName = "Card";

export const CardHeader = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex items-start justify-between gap-4 px-5 pt-5", className)} {...props} />
);

export const CardTitle = ({ className, ...props }: React.HTMLAttributes<HTMLHeadingElement>) => (
  <h3 className={cn("font-display text-[15px] font-semibold tracking-tight text-fg", className)} {...props} />
);

export const CardDescription = ({ className, ...props }: React.HTMLAttributes<HTMLParagraphElement>) => (
  <p className={cn("text-[13px] leading-5 text-fg-muted", className)} {...props} />
);

export const CardContent = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("px-5 pt-4 pb-5", className)} {...props} />
);

export const CardFooter = ({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) => (
  <div className={cn("flex items-center gap-3 border-t border-line px-5 py-3", className)} {...props} />
);
