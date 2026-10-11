import type { Level } from "@/lib/types";
import { cn } from "@/lib/utils";

const STYLE: Record<Level, { dot: string; text: string; bg: string }> = {
  observe: { dot: "bg-[#1d7a4a]", text: "text-[#17653d]", bg: "bg-[#e7f3ec]" },
  anomaly: { dot: "bg-[#c49214]", text: "text-[#8a6710]", bg: "bg-[#f8efd4]" },
  risk: { dot: "bg-[#c24532]", text: "text-[#9d3428]", bg: "bg-[#fde8e4]" },
};

export function StatusPill({ level, label }: { level: Level; label: string }) {
  const style = STYLE[level];
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-medium", style.bg, style.text)}>
      <span className={cn("h-1.5 w-1.5 rounded-full", style.dot, level !== "observe" && "motion-safe:animate-pulse")} />
      {label}
    </span>
  );
}
