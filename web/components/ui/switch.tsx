"use client";

import * as Switch from "@radix-ui/react-switch";
import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

export function SwitchToggle({ className, ...props }: ComponentProps<typeof Switch.Root>) {
  return (
    <Switch.Root
      className={cn(
        "inline-flex h-6 w-11 shrink-0 cursor-pointer items-center rounded-full transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#1c1915] focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-[#1d7a4a] data-[state=unchecked]:bg-[#d9d1c3]",
        className,
      )}
      {...props}
    >
      <Switch.Thumb className="pointer-events-none block h-5 w-5 translate-x-0.5 rounded-full bg-white shadow transition-transform data-[state=checked]:translate-x-5" />
    </Switch.Root>
  );
}
