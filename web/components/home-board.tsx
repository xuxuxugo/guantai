"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { MarketStrip } from "@/components/market-strip";
import { ErrorNote, LoadingBlock } from "@/components/desk-ui";
import { StockLink } from "@/components/stock-link";
import { api, errorMessage } from "@/lib/api";
import { formatPct, priceTone } from "@/lib/format";
import type { MarketOverview, PoolSnapshot, WatchlistResponse } from "@/lib/types";

export function HomeBoard() {
  const [market, setMarket] = useState<MarketOverview | null>(null);
  const [pool, setPool] = useState<PoolSnapshot | null>(null);
  const [watch, setWatch] = useState<WatchlistResponse | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let stop = false;
    Promise.allSettled([api.market(), api.pool(), api.watchlist()]).then(([marketResult, poolResult, watchResult]) => {
      if (stop) return;
      if (marketResult.status === "fulfilled") setMarket(marketResult.value);
      if (poolResult.status === "fulfilled") setPool(poolResult.value);
      if (watchResult.status === "fulfilled") setWatch(watchResult.value);
      const failed = [marketResult, poolResult, watchResult].find((item) => item.status === "rejected");
      setError(failed && failed.status === "rejected" ? errorMessage(failed.reason, "有一块数据没有回来") : "");
      setLoading(false);
    });
    return () => {
      stop = true;
    };
  }, []);

  return (
    <div className="space-y-5">
      <MarketStrip data={market} loading={loading} error="" />
      <ErrorNote text={error} />
      <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="font-medium">板块涨跌</h2>
          <Link href="/overview" className="text-sm text-[#6f675c] underline-offset-4 hover:underline">
            市场概览
          </Link>
        </div>
        {loading && !pool && <div className="mt-3"><LoadingBlock /></div>}
        {pool && (
          <>
            <div className="mt-3 flex flex-wrap gap-2">
              {pool.sectors.map((item) => (
                <span key={item.sector} className={`rounded-full bg-white px-3 py-1 text-sm ${priceTone(item.change_pct)}`}>
                  {item.sector} {formatPct(item.change_pct)}
                </span>
              ))}
            </div>
            <ul className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6">
              {pool.rows.filter((row) => row.price > 0).map((row) => (
                <li key={row.code}>
                  <StockLink
                    code={row.code}
                    name={row.name}
                    to="info"
                    className="block rounded-lg px-2 py-3 text-center text-white transition-transform hover:scale-[1.02] active:scale-[0.98]"
                    style={{ background: heat(row.change_pct) }}
                  >
                    <p className="truncate text-sm">{row.name}</p>
                    <p className="num mt-1 text-sm">{formatPct(row.change_pct)}</p>
                  </StockLink>
                </li>
              ))}
            </ul>
            <p className="mt-3 text-xs leading-5 text-[#6f675c]">{pool.note}{pool.stale ? " 行情延迟，显示上次成功报价。" : ""}</p>
          </>
        )}
      </section>
      <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
        <div className="flex items-baseline justify-between gap-3">
          <h2 className="font-medium">自选摘要</h2>
          <Link href="/watch" className="text-sm text-[#6f675c] underline-offset-4 hover:underline">
            打开盯盘台
          </Link>
        </div>
        {watch && watch.items.length === 0 && <p className="mt-3 text-sm text-[#6f675c]">自选还是空的。</p>}
        {watch && watch.items.length > 0 && (
          <ul className="mt-3 divide-y divide-[#eee6d8]">
            {watch.items.slice(0, 6).map((item) => (
              <li key={item.code} className="flex items-center justify-between gap-3 py-2 text-sm">
                <StockLink code={item.code} name={item.name} className="font-medium underline-offset-4 hover:underline">
                  {item.name}
                </StockLink>
                <span className={priceTone(item.change_pct)}>{formatPct(item.change_pct)}</span>
                <span className="text-[#6f675c]">{item.latest_signal}</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function heat(change: number) {
  if (change >= 2) return "#9d3428";
  if (change > 0) return "#c24532";
  if (change <= -2) return "#17653d";
  if (change < 0) return "#1d7a4a";
  return "#6f675c";
}
