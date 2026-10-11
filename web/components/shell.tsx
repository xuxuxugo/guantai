"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { createContext, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "@/lib/api";
import { formatClock, formatTime, priceTone, formatPct, formatPrice } from "@/lib/format";
import { researchHref, StockProvider, useStock } from "@/lib/stock-context";
import type { AlertEvent, Meta } from "@/lib/types";
import { isResearchPath, ResearchTabs } from "@/components/research-tabs";
import { StatusPill } from "@/components/status-pill";
import { Input } from "@/components/ui/input";

type LiveState = {
  revision: number;
  meta: Meta | null;
};

const LiveContext = createContext<LiveState>({ revision: 0, meta: null });

export function useLive() {
  return useContext(LiveContext);
}

type NavItem = { href: string; label: string };
type NavGroup = { id: string; label: string; items: NavItem[] };

const NAV_GROUPS: NavGroup[] = [
  {
    id: "desk",
    label: "盯盘",
    items: [
      { href: "/", label: "首页" },
      { href: "/watch", label: "盯盘台" },
      { href: "/alerts", label: "告警流" },
      { href: "/rules", label: "规则中心" },
    ],
  },
  {
    id: "research",
    label: "研究",
    items: [
      { href: "/info", label: "个股信息" },
      { href: "/technical", label: "技术分析" },
      { href: "/financial", label: "财务分析" },
      { href: "/quant", label: "量化策略" },
      { href: "/agent", label: "AI分析" },
    ],
  },
  {
    id: "market",
    label: "市场",
    items: [
      { href: "/overview", label: "市场概览" },
      { href: "/data", label: "数据中心" },
      { href: "/calendar", label: "财经日历" },
      { href: "/news", label: "实时新闻" },
    ],
  },
  {
    id: "discover",
    label: "发现",
    items: [
      { href: "/screen", label: "选股" },
      { href: "/digest", label: "策略日报" },
      { href: "/opportunities", label: "投资机会" },
    ],
  },
  {
    id: "me",
    label: "我的",
    items: [{ href: "/me", label: "我的" }],
  },
];

const FLAT_NAV = NAV_GROUPS.flatMap((group) => group.items);

function active(path: string, href: string) {
  if (href === "/") return path === "/";
  return path === href || path.startsWith(`${href}/`);
}

function groupActive(path: string, group: NavGroup) {
  return group.items.some((item) => active(path, item.href));
}

function scanSeconds(meta: Meta) {
  const offhours = meta.offhours_scan_interval_seconds ?? 60;
  if (meta.quote_source === "mock" || meta.trading_session_open) return meta.scan_interval_seconds;
  return offhours;
}

function titleFor(path: string) {
  if (path.startsWith("/stocks/")) return "盯盘详情";
  return FLAT_NAV.find((item) => active(path, item.href))?.label ?? "观澜";
}

function Mark() {
  return (
    <svg viewBox="0 0 32 32" aria-hidden="true" className="h-7 w-7">
      <rect width="32" height="32" rx="7" fill="#c24532" />
      <path d="M6 13c2 0 2-3 4-3s2 3 4 3 2-3 4-3 2 3 4 3 2-3 4-3" fill="none" stroke="#f6f1e7" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M6 20c2 0 2-3 4-3s2 3 4 3 2-3 4-3 2 3 4 3 2-3 4-3" fill="none" stroke="#1c1915" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

function GlobalStockSearch() {
  const path = usePathname();
  const router = useRouter();
  const { code, name, setStock } = useStock();
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<{ code: string; name: string }[]>([]);
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const keyword = query.trim();
    if (!keyword) {
      setHits([]);
      return;
    }
    const timer = window.setTimeout(() => {
      api.search(keyword).then((result) => setHits(result.items)).catch(() => setHits([]));
    }, 180);
    return () => window.clearTimeout(timer);
  }, [query]);

  useEffect(() => {
    function onDoc(event: MouseEvent) {
      if (!wrapRef.current?.contains(event.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, []);

  function pick(hit: { code: string; name: string }) {
    setStock(hit.code, hit.name);
    setQuery("");
    setHits([]);
    setOpen(false);
    const dest = isResearchPath(path)
      ? path.startsWith("/stocks/")
        ? `/stocks/${hit.code}`
        : researchHref(path.split("?")[0], hit.code)
      : researchHref("/info", hit.code);
    router.push(dest);
  }

  return (
    <div ref={wrapRef} className="relative min-w-0 flex-1 max-w-md">
      <label className="sr-only" htmlFor="global-stock-search">
        全局选股
      </label>
      <Input
        id="global-stock-search"
        className="h-9 border-[#3a342c] bg-[#2a2520] text-[#f3efe6] placeholder:text-[#8a8174] focus-visible:ring-[#c24532]"
        value={query}
        placeholder={name ? `${name} ${code}` : `选股 · 当前 ${code}`}
        onChange={(event) => {
          setQuery(event.target.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
      />
      {open && hits.length > 0 && (
        <ul className="absolute top-full z-50 mt-1 max-h-72 w-full overflow-auto rounded-lg border border-[#3a342c] bg-[#241f1a] shadow-xl">
          {hits.map((hit) => (
            <li key={hit.code}>
              <button
                type="button"
                className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left text-sm text-[#f3efe6] hover:bg-white/10"
                onClick={() => pick(hit)}
              >
                <span>{hit.name}</span>
                <span className="num text-[#cfc6b6]">{hit.code}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function GroupedNav() {
  const path = usePathname();
  const { code } = useStock();
  const [openId, setOpenId] = useState<string | null>(null);

  return (
    <nav className="flex items-stretch gap-0.5 overflow-x-auto px-2 pb-2 md:px-4" aria-label="主导航">
      {NAV_GROUPS.map((group) => {
        const on = groupActive(path, group);
        const expanded = openId === group.id;
        if (group.items.length === 1) {
          const item = group.items[0];
          return (
            <Link
              key={group.id}
              href={item.href}
              className={`rounded-md px-3 py-2 text-sm whitespace-nowrap ${on ? "bg-white/10 text-white" : "text-[#d9d0c1] hover:bg-white/5 hover:text-white"}`}
              aria-current={on ? "page" : undefined}
            >
              {item.label}
            </Link>
          );
        }
        return (
          <div
            key={group.id}
            className="relative"
            onMouseEnter={() => setOpenId(group.id)}
            onMouseLeave={() => setOpenId((cur) => (cur === group.id ? null : cur))}
          >
            <button
              type="button"
              className={`flex items-center gap-1 rounded-md px-3 py-2 text-sm whitespace-nowrap ${on ? "bg-white/10 text-white" : "text-[#d9d0c1] hover:bg-white/5 hover:text-white"}`}
              aria-expanded={expanded}
              onClick={() => setOpenId(expanded ? null : group.id)}
            >
              {group.label}
              <span className="text-[10px] opacity-70" aria-hidden>
                ▾
              </span>
            </button>
            {expanded && (
              <div className="absolute top-full left-0 z-40 min-w-[9.5rem] rounded-lg border border-[#3a342c] bg-[#241f1a] py-1 shadow-xl">
                {group.items.map((item) => {
                  const itemOn = active(path, item.href);
                  const href =
                    group.id === "research" ? researchHref(item.href, code) : item.href;
                  return (
                    <Link
                      key={item.href}
                      href={href}
                      className={`block px-3 py-2 text-sm whitespace-nowrap ${itemOn ? "bg-white/10 text-white" : "text-[#d9d0c1] hover:bg-white/5 hover:text-white"}`}
                      aria-current={itemOn ? "page" : undefined}
                      onClick={() => setOpenId(null)}
                    >
                      {item.label}
                    </Link>
                  );
                })}
              </div>
            )}
          </div>
        );
      })}
    </nav>
  );
}

function ShellInner({ children }: { children: ReactNode }) {
  const path = usePathname();
  const { code, name, setStock } = useStock();
  const [revision, setRevision] = useState(0);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [clock, setClock] = useState("");
  const [channel, setChannel] = useState<"连接中" | "已连接" | "重连中">("连接中");
  const [toast, setToast] = useState<AlertEvent | null>(null);
  const research = isResearchPath(path);

  useEffect(() => {
    const tick = () => setClock(formatClock(new Date()));
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, []);

  useEffect(() => {
    let stop = false;
    api.meta().then((data) => {
      if (!stop) setMeta(data);
    }).catch(() => {
      if (!stop) setMeta(null);
    });
    return () => {
      stop = true;
    };
  }, []);

  useEffect(() => {
    const source = new EventSource("/stream");
    source.onopen = () => setChannel("已连接");
    source.onerror = () => setChannel("重连中");
    source.addEventListener("alert", (event) => {
      try {
        const data = JSON.parse((event as MessageEvent<string>).data) as AlertEvent;
        setToast(data);
        setRevision((value) => value + 1);
      } catch {
        setRevision((value) => value + 1);
      }
    });
    return () => source.close();
  }, []);

  useEffect(() => {
    if (!toast) return;
    const timer = window.setTimeout(() => setToast(null), 8000);
    return () => window.clearTimeout(timer);
  }, [toast]);

  return (
    <LiveContext.Provider value={{ revision, meta }}>
      <div className="min-h-screen">
        <div className="sticky top-0 z-30 bg-[#1c1915] text-[#f3efe6]">
          <div className="flex flex-wrap items-center gap-3 px-3 py-2.5 md:px-5">
            <Link href="/" className="flex shrink-0 items-center gap-2">
              <Mark />
              <span className="font-serif text-lg leading-none tracking-wide">观澜</span>
            </Link>
            <GlobalStockSearch />
            <div className="ml-auto flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-[#cfc6b6]">
              <span className="hidden sm:inline">
                {meta?.session_label ?? "行情"}
                {meta ? ` · ${scanSeconds(meta)}s` : ""}
              </span>
              <span>
                <span className="num text-[#f3efe6]">{clock || "--:--:--"}</span>
                <span className="mx-1.5 text-[#5c5348]">·</span>
                {channel}
              </span>
            </div>
          </div>
          <GroupedNav />
        </div>
        <header className="border-b border-[#e0d8c8] bg-[#f3efe6] px-4 py-3 shadow-[inset_0_2px_0_#c24532] md:px-8">
          <div className="flex flex-wrap items-end justify-between gap-2">
            <div>
              <p className="text-xs text-[#6f675c]">
                {research && (name || code) ? (
                  <>
                    当前标的 <span className="text-[#1c1915]">{name || "股票"}</span>{" "}
                    <span className="num">{code}</span>
                    <span className="mx-1.5 text-[#d9d0c1]">·</span>
                  </>
                ) : null}
                {meta?.market ?? "腾讯行情"}
                {meta?.demo_auto_pulse ? " · 演示脉冲" : ""}
              </p>
              <h1 className="mt-0.5 font-serif text-xl md:text-2xl">{titleFor(path)}</h1>
            </div>
            <p className="max-w-xs text-right text-[11px] leading-4 text-[#8a8174]">
              仅供研究参考，不构成投资建议
            </p>
          </div>
          {research && (
            <div className="mt-3">
              <ResearchTabs code={code} />
            </div>
          )}
        </header>
        <main className="px-4 py-5 md:px-8">{children}</main>
      </div>
      {toast && (
        <div className="fixed right-3 bottom-3 left-3 z-40 max-w-md rounded-xl border border-[#e0d8c8] bg-[#fffaf3] p-4 shadow-lg md:left-auto">
          <div className="flex items-center justify-between gap-3">
            <p className="text-xs text-[#6f675c]">新告警 · {formatTime(toast.created_at)}</p>
            <StatusPill level={toast.level} label={toast.level_label} />
          </div>
          <p className="mt-1 font-medium">
            {toast.name} · {toast.title}
          </p>
          <p className="mt-1 text-sm leading-6 text-[#3c372f]">{toast.reason}</p>
          <p className={`num mt-1 text-sm ${priceTone(toast.change_pct)}`}>
            {formatPrice(toast.price)} {formatPct(toast.change_pct)}
          </p>
          <div className="mt-3 flex gap-4 text-sm">
            <Link href="/alerts" className="underline underline-offset-4" onClick={() => setToast(null)}>
              去告警流
            </Link>
            <Link
              href={researchHref("/info", toast.code)}
              className="underline underline-offset-4"
              onClick={() => {
                setStock(toast.code, toast.name);
                setToast(null);
              }}
            >
              研究这只
            </Link>
            <button type="button" className="text-[#6f675c]" onClick={() => setToast(null)}>
              知道了
            </button>
          </div>
        </div>
      )}
    </LiveContext.Provider>
  );
}

export function Shell({ children }: { children: ReactNode }) {
  return (
    <StockProvider>
      <ShellInner>{children}</ShellInner>
    </StockProvider>
  );
}
