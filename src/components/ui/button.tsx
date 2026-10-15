import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex shrink-0 items-center justify-center gap-2 whitespace-nowrap font-medium transition-[background-color,color,border-color,box-shadow,transform] duration-200 ease-[var(--ease-out-cubic)] select-none active:scale-[0.98] disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-signal text-asphalt-900 hover:bg-signal-400 active:bg-signal-600 shadow-[0_8px_24px_-12px_rgb(255_91_31/0.8)]",
        secondary: "bg-surface-2 text-fg hover:bg-surface-3 border border-line",
        outline: "border border-line-strong bg-transparent text-fg hover:bg-surface-2",
        ghost: "bg-transparent text-fg-muted hover:bg-surface-2 hover:text-fg",
        glass: "border border-white/14 bg-white/[0.06] text-paper backdrop-blur-md hover:bg-white/[0.12]",
        paper: "bg-paper text-asphalt-900 hover:bg-white",
        link: "h-auto px-0 text-accent-ink underline-offset-4 hover:underline active:scale-100",
      },
      size: {
        sm: "h-8 rounded-lg px-3 text-[13px] [&_svg]:size-3.5",
        md: "h-10 rounded-xl px-4 text-sm [&_svg]:size-4",
        lg: "h-12 rounded-2xl px-6 text-[15px] [&_svg]:size-[18px]",
        xl: "h-14 rounded-full px-7 text-base [&_svg]:size-5",
        icon: "size-10 rounded-xl [&_svg]:size-[18px]",
        "icon-sm": "size-8 rounded-lg [&_svg]:size-4",
      },
      pill: { true: "rounded-full" },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, pill, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button";
  return <Comp ref={ref} className={cn(buttonVariants({ variant, size, pill }), className)} {...props} />;
});
Button.displayName = "Button";

export { Button, buttonVariants };
