"use client";

import * as Menu from "@radix-ui/react-dropdown-menu";
import * as React from "react";
import { cn } from "@/lib/utils";

export const DropdownMenu = Menu.Root;
export const DropdownMenuTrigger = Menu.Trigger;
export const DropdownMenuGroup = Menu.Group;

export const DropdownMenuContent = React.forwardRef<React.ElementRef<typeof Menu.Content>, React.ComponentPropsWithoutRef<typeof Menu.Content>>(
  ({ className, sideOffset = 8, align = "end", ...props }, ref) => (
    <Menu.Portal>
      <Menu.Content
        ref={ref}
        sideOffset={sideOffset}
        align={align}
        className={cn("z-50 min-w-56 rounded-2xl border border-line bg-surface p-1.5 text-fg shadow-[var(--shadow-lift)]", className)}
        {...props}
      />
    </Menu.Portal>
  ),
);
DropdownMenuContent.displayName = "DropdownMenuContent";

export const DropdownMenuItem = React.forwardRef<React.ElementRef<typeof Menu.Item>, React.ComponentPropsWithoutRef<typeof Menu.Item>>(
  ({ className, ...props }, ref) => (
    <Menu.Item
      ref={ref}
      className={cn(
        "flex cursor-pointer items-center gap-2.5 rounded-xl px-2.5 py-2 text-[13px] text-fg-muted outline-none select-none data-[highlighted]:bg-surface-2 data-[highlighted]:text-fg [&_svg]:size-4",
        className,
      )}
      {...props}
    />
  ),
);
DropdownMenuItem.displayName = "DropdownMenuItem";

export const DropdownMenuLabel = ({ className, ...props }: React.ComponentPropsWithoutRef<typeof Menu.Label>) => (
  <Menu.Label className={cn("px-2.5 pt-1.5 pb-1 label-mono text-fg-subtle", className)} {...props} />
);

export const DropdownMenuSeparator = ({ className, ...props }: React.ComponentPropsWithoutRef<typeof Menu.Separator>) => (
  <Menu.Separator className={cn("my-1 h-px bg-line", className)} {...props} />
);
