"use client";

import { useEffect, useState } from "react";
import { useLive } from "@/components/shell";
import { StatusPill } from "@/components/status-pill";
import { StockLink } from "@/components/stock-link";
import { api, errorMessage } from "@/lib/api";
import { formatPct, formatPrice, formatTime, priceTone } from "@/lib/format";
import type { AlertEvent, Level } from "@/lib/types";
import { cn } from "@/lib/utils";

const FILTERS: { id: "all" | Level; label: string }[] = [
  { id: "all", label: "全部" },
  { id: "observe", label: "观察" },
  { id: "anomaly", label: "异动" },
  { id: "risk", label: "风控" },
];

export function AlertStream() {
  const { revision } = useLive();
  const [events, setEvents] = useState<AlertEvent[] | null>(null);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState<(typeof FILTERS)[number]["id"]>("all");

  useEffect(() => {
    let stop = false;
    async function load() {
      try {
        const data = await api.alerts();
        if (!stop) {
          setEvents(data.events);
          setError("");
        }
      } catch (err) {
        if (!stop) setError(errorMessage(err, "告警暂时没有取到，正在重试。"));
      }
    }
    void load();
    const timer = window.setInterval(() => void load(), 5000);
    return () => {
      stop = true;
      window.clearInterval(timer);
    };
  }, [revision]);

  const visible = (events ?? []).filter((item) => filter === "all" || item.level === filter);
  const counts = {
    all: events?.length ?? 0,
    observe: events?.filter((item) => item.level === "observe").length ?? 0,
    anomaly: events?.filter((item) => item.level === "anomaly").length ?? 0,
    risk: events?.filter((item) => item.level === "risk").length ?? 0,
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-2">
        {FILTERS.map((item) => (
          <button
            key={item.id}
            type="button"
            onClick={() => setFilter(item.id)}
            className={cn(
              "rounded-full border px-3 py-1 text-sm",
              filter === item.id ? "border-[#1c1915] bg-[#1c1915] text-[#f6f1e7]" : "border-[#d9d0c1] bg-[#fbf8f2] text-[#3c372f]",
            )}
          >
            {item.label} {counts[item.id]}
          </button>
        ))}
      </div>
      {error && <p className="rounded-md bg-[#f7e7e2] px-3 py-2 text-sm text-[#8d3428]">{error}</p>}
      {events === null && !error && (
        <div className="space-y-3" aria-busy="true">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-24 animate-pulse rounded-xl bg-[#e7e1d6]" />
          ))}
        </div>
      )}
      {events && visible.length === 0 && (
        <div className="rounded-xl border border-dashed border-[#d9d0c1] bg-[#fbf8f2] px-4 py-10 text-center">
          <p className="font-medium">{filter === "all" ? "这段时间没有告警" : "这个级别暂时没有告警"}</p>
          <p className="mt-1 text-sm text-[#6f675c]">规则在扫描里看着。交易时段的价格变动会写到这里。</p>
        </div>
      )}
      {visible.length > 0 && (
        <ol className="relative ml-3 space-y-4 border-l border-[#e0d8c8]">
          {visible.map((event) => (
            <li key={event.id} className="ml-6">
              <span
                className={cn(
                  "absolute -left-1.5 mt-5 h-3 w-3 rounded-full",
                  event.level === "risk" && "bg-[#c24532]",
                  event.level === "anomaly" && "bg-[#c49214]",
                  event.level === "observe" && "bg-[#1d7a4a]",
                )}
              />
              <article className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
                <div className="flex flex-wrap items-center gap-2 text-xs text-[#6f675c]">
                  <time dateTime={event.created_at}>{formatTime(event.created_at)}</time>
                  <StatusPill level={event.level} label={event.level_label} />
                  <span className="num">{event.code}</span>
                </div>
                <h2 className="mt-1 font-medium">
                  {event.name} · {event.title}
                </h2>
                <p className="mt-1 text-sm leading-6 text-[#3c372f]">{event.reason}</p>
                <div className="mt-3 flex items-center justify-between gap-3">
                  <span className={cn("num text-sm", priceTone(event.change_pct))}>
                    {formatPrice(event.price)} {formatPct(event.change_pct)}
                  </span>
                  <StockLink code={event.code} name={event.name} className="text-sm underline underline-offset-4">
                    研究这只
                  </StockLink>
                </div>
              </article>
            </li>
          ))}
        </ol>
      )}
      <p className="text-xs leading-5 text-[#6f675c]">仅供研究参考，不构成投资建议。同一规则会用 Redis 去重，避免每次扫描都刷一条。</p>
    </div>
  );
}
