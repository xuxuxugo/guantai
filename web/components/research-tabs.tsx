"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { researchHref, useStock } from "@/lib/stock-context";

const TABS = [
  { href: "/info", label: "个股信息" },
  { href: "/technical", label: "技术分析" },
  { href: "/financial", label: "财务分析" },
  { href: "/quant", label: "量化策略" },
  { href: "/agent", label: "AI分析" },
  { href: "/stocks", label: "盯盘详情" },
];

function active(path: string, href: string) {
  if (href === "/stocks") return path.startsWith("/stocks/");
  return path === href || path.startsWith(`${href}/`);
}

export function ResearchTabs({ code }: { code?: string }) {
  const path = usePathname();
  const stock = useStock();
  const activeCode = code || stock.code;

  return (
    <nav
      className="flex gap-1 overflow-x-auto rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-1"
      aria-label="研究模块"
    >
      {TABS.map((tab) => {
        const on = active(path, tab.href);
        return (
          <Link
            key={tab.href}
            href={researchHref(tab.href, activeCode)}
            className={`rounded-lg px-3 py-2 text-sm whitespace-nowrap transition-colors ${
              on ? "bg-[#1c1915] text-[#f3efe6]" : "text-[#3c372f] hover:bg-[#f0e9dc]"
            }`}
            aria-current={on ? "page" : undefined}
          >
            {tab.label}
          </Link>
        );
      })}
    </nav>
  );
}

export function isResearchPath(path: string) {
  return (
    path.startsWith("/info") ||
    path.startsWith("/technical") ||
    path.startsWith("/financial") ||
    path.startsWith("/quant") ||
    path.startsWith("/agent") ||
    path.startsWith("/stocks/")
  );
}
