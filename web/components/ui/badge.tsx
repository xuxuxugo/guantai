import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Badge({ className, children }: { className?: string; children: ReactNode }) {
  return (
    <span className={cn("inline-flex items-center rounded-full border border-[#e0d8c8] bg-[#f7f1e6] px-2 py-0.5 text-xs text-[#6f675c]", className)}>
      {children}
    </span>
  );
}
