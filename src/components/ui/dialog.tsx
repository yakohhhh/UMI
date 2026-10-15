"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> & { title: string; description?: string }
>(({ className, children, title, description, ...props }, ref) => (
  <DialogPrimitive.Portal>
    <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-asphalt-950/60 backdrop-blur-sm" />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        "fixed top-1/2 left-1/2 z-50 w-[calc(100%-32px)] max-w-md -translate-x-1/2 -translate-y-1/2 rounded-3xl border border-line bg-surface p-6 text-fg shadow-[var(--shadow-lift)]",
        className,
      )}
      {...props}
    >
      <DialogPrimitive.Title className="font-display text-lg font-semibold">{title}</DialogPrimitive.Title>
      {description ? <DialogPrimitive.Description className="mt-1.5 text-sm text-fg-muted">{description}</DialogPrimitive.Description> : null}
      <div className="mt-5">{children}</div>
      <DialogPrimitive.Close className="absolute top-4 right-4 rounded-lg p-1.5 text-fg-muted hover:bg-surface-2 hover:text-fg" aria-label="Close">
        <X className="size-4" />
      </DialogPrimitive.Close>
    </DialogPrimitive.Content>
  </DialogPrimitive.Portal>
));
DialogContent.displayName = "DialogContent";
