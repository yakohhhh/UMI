"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";

export const Sheet = DialogPrimitive.Root;
export const SheetTrigger = DialogPrimitive.Trigger;
export const SheetClose = DialogPrimitive.Close;

/**
 * Bottom (mobile) or side drawer built on the Radix dialog: focus is trapped,
 * Escape and the backdrop close it, the title is announced.
 */
export const SheetContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & {
    title: string;
    description?: string;
    side?: "bottom" | "right";
    /** Keep the title for screen readers only (the content has its own heading). */
    hideHeader?: boolean;
  }
>(({ className, children, title, description, side = "bottom", hideHeader, onOpenAutoFocus, ...props }, ref) => (
  <DialogPrimitive.Portal>
    <DialogPrimitive.Overlay className="umi-sheet-overlay fixed inset-0 z-50 bg-asphalt-950/55 backdrop-blur-[2px]" />
    <DialogPrimitive.Content
      ref={ref}
      data-side={side}
      onOpenAutoFocus={(e) => {
        onOpenAutoFocus?.(e);
        if (e.defaultPrevented) return;
        // Focus the drawer itself rather than its first field, so phones don't pop the keyboard open.
        e.preventDefault();
        (e.currentTarget as HTMLElement | null)?.focus();
      }}
      className={cn(
        "umi-sheet fixed z-50 flex flex-col border-line bg-surface text-fg shadow-[var(--shadow-lift)] outline-none",
        side === "bottom" ? "inset-x-0 bottom-0 max-h-[86dvh] rounded-t-3xl border-t pb-[env(safe-area-inset-bottom)]" : "inset-y-0 right-0 w-[min(440px,100vw)] border-l",
        className,
      )}
      {...props}
    >
      {side === "bottom" ? <div className="mx-auto mt-2.5 h-1 w-10 shrink-0 rounded-full bg-line-strong" aria-hidden /> : null}
      <div className={cn("shrink-0 px-5 pt-4 pr-14", hideHeader && "sr-only")}>
        <DialogPrimitive.Title className="font-display text-lg font-semibold">{title}</DialogPrimitive.Title>
        {description ? <DialogPrimitive.Description className="mt-1 text-sm text-fg-muted">{description}</DialogPrimitive.Description> : null}
      </div>
      {!description ? <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description> : null}
      <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-5 pt-3 pb-6">{children}</div>
      <DialogPrimitive.Close className="absolute top-4 right-4 rounded-lg p-1.5 text-fg-muted hover:bg-surface-2 hover:text-fg" aria-label="Close">
        <X className="size-4" />
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
SheetContent.displayName = "SheetContent";
