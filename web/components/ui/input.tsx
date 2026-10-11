import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

export function Input({ className, ...props }: ComponentProps<"input">) {
  return (
    <input
      className={cn(
        "flex h-10 w-full rounded-md border border-[#d9d0c1] bg-white px-3 text-sm text-[#1c1915] outline-none placeholder:text-[#958c80] focus-visible:ring-2 focus-visible:ring-[#1c1915]",
        className,
      )}
      {...props}
    />
  );
}
