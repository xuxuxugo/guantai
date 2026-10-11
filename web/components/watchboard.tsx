"use client";

import { useEffect, useRef, useState } from "react";
import { MarketStrip } from "@/components/market-strip";
import { ShockPad } from "@/components/shock-pad";
import { StatusPill } from "@/components/status-pill";
import { StockLink } from "@/components/stock-link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, errorMessage } from "@/lib/api";
import { formatPct, formatPrice, priceTone } from "@/lib/format";
import type { MarketOverview, WatchItem, WatchlistResponse } from "@/lib/types";
import { useLive } from "@/components/shell";

export function Watchboard() {
  const { revision, meta } = useLive();
  const [data, setData] = useState<WatchlistResponse | null>(null);
  const [market, setMarket] = useState<MarketOverview | null>(null);
  const [marketError, setMarketError] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<{ code: string; name: string }[]>([]);
  const [adding, setAdding] = useState("");
  const [addError, setAddError] = useState("");
  const searchSeq = useRef(0);

  async function load() {
    const [listResult, marketResult] = await Promise.allSettled([api.watchlist(), api.market()]);
    if (listResult.status === "fulfilled") {
      setData(listResult.value);
      setError("");
    } else {
      setError(errorMessage(listResult.reason, "行情服务暂时没有回应，正在重试。"));
    }
    if (marketResult.status === "fulfilled") {
      setMarket(marketResult.value);
      setMarketError("");
    } else {
      setMarketError(errorMessage(marketResult.reason, "大盘暂时没有回应，正在重试。"));
    }
    setLoading(false);
  }

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), 4000);
    return () => window.clearInterval(timer);
  }, [revision]);

  useEffect(() => {
    const keyword = query.trim();
    if (!keyword) {
      setHits([]);
      return;
    }
    const seq = ++searchSeq.current;
    const timer = window.setTimeout(() => {
      api.search(keyword).then((result) => {
        if (searchSeq.current === seq) setHits(result.items);
      }).catch(() => {
        if (searchSeq.current === seq) setHits([]);
      });
    }, 200);
    return () => window.clearTimeout(timer);
  }, [query]);

  async function add(code: string) {
    setAdding(code);
    setAddError("");
    try {
      await api.addWatch(code);
      setQuery("");
      setHits([]);
      await load();
    } catch (err) {
      setAddError(errorMessage(err, "没有加入盯盘台"));
    } finally {
      setAdding("");
    }
  }

  async function remove(code: string) {
    setAddError("");
    try {
      await api.removeWatch(code);
      await load();
    } catch (err) {
      setAddError(errorMessage(err, "没有移出盯盘台"));
    }
  }

  const items = data?.items ?? [];

  return (
    <div className="space-y-5">
      <MarketStrip data={market} loading={loading} error={marketError} />
      <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
        <div className="flex flex-col gap-3 md:flex-row md:items-end">
          <label className="block flex-1 text-sm">
            <span className="mb-1 block text-[#6f675c]">搜索代码或名称</span>
            <Input
              value={query}
              placeholder="试试 600519 或 茅台"
              onChange={(event) => setQuery(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && hits[0]) void add(hits[0].code);
              }}
            />
          </label>
          <Button disabled={!hits[0] || adding !== ""} onClick={() => hits[0] && void add(hits[0].code)}>
            {adding ? "加入中…" : "加入盯盘"}
          </Button>
        </div>
        {hits.length > 0 && (
          <ul className="mt-3 divide-y divide-[#eee6d8] rounded-md border border-[#eee6d8] bg-white">
            {hits.map((hit) => (
              <li key={hit.code} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
                <span>
                  <span className="num mr-2 text-[#6f675c]">{hit.code}</span>
                  {hit.name}
                </span>
                <Button size="sm" variant="outline" disabled={adding !== ""} onClick={() => void add(hit.code)}>
                  加入
                </Button>
              </li>
            ))}
          </ul>
        )}
        {query.trim() && hits.length === 0 && <p className="mt-3 text-sm text-[#6f675c]">没有找到这只股票。试试 6 位代码，或「茅台」。</p>}
        {addError && <p className="mt-3 text-sm text-[#9d3428]">{addError}</p>}
      </section>

      <div className="flex flex-wrap items-center gap-2 text-xs text-[#6f675c]">
        <Badge>{(data?.quote_source ?? meta?.quote_source) === "mock" ? "模拟行情" : "腾讯行情"}</Badge>
        {data?.session_label && <span>{data.session_label}</span>}
        {data?.quote_stale && <span>行情延迟，显示上次成功报价</span>}
        <span>价格红涨绿跌。状态灯：绿观察、黄异动、红风控。</span>
        {data && (
          <span>
            {data.trading_hours_only
              ? data.trading_session_open
                ? "仅交易时段出警 · 当前在交易时段"
                : "仅交易时段出警 · 当前休市，自动扫描暂停写告警"
              : "全天按规则出警，方便演示"}
          </span>
        )}
      </div>

      {loading && !data && (
        <div className="space-y-2" aria-busy="true">
          {Array.from({ length: 4 }).map((_, index) => (
            <div key={index} className="h-14 animate-pulse rounded-lg bg-[#e7e1d6]" />
          ))}
        </div>
      )}
      {error && <p className="rounded-md bg-[#f7e7e2] px-3 py-2 text-sm text-[#8d3428]">{error}</p>}

      {!loading && items.length === 0 && (
        <div className="rounded-xl border border-dashed border-[#d9d0c1] bg-[#fbf8f2] px-4 py-10 text-center">
          <p className="font-medium">还没有自选</p>
          <p className="mt-1 text-sm text-[#6f675c]">搜索代码或名称，把股票放进盯盘台。</p>
        </div>
      )}

      {items.length > 0 && (
        <>
          <div className="hidden overflow-hidden rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] md:block">
            <table className="w-full text-sm">
              <caption className="sr-only">自选股盯盘</caption>
              <thead className="bg-[#f7f1e6] text-left text-xs text-[#6f675c]">
                <tr>
                  <th className="px-4 py-3 font-medium">状态</th>
                  <th className="px-3 py-3 font-medium">代码</th>
                  <th className="px-3 py-3 font-medium">名称</th>
                  <th className="px-3 py-3 text-right font-medium">最新价</th>
                  <th className="px-3 py-3 text-right font-medium">涨跌幅</th>
                  <th className="px-3 py-3 font-medium">最新信号</th>
                  <th className="px-4 py-3 font-medium">操作</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.code} className="border-t border-[#eee6d8]">
                    <td className="px-4 py-3">
                      <StatusPill level={item.status} label={item.status_label} />
                    </td>
                    <td className="num px-3 py-3">{item.code}</td>
                    <td className="px-3 py-3">
                      <StockLink code={item.code} name={item.name} className="underline-offset-4 hover:underline">
                        {item.name}
                      </StockLink>
                      <span className="mx-2 text-[#d9d0c1]">·</span>
                      <StockLink code={item.code} name={item.name} to="detail" className="text-xs text-[#6f675c] underline-offset-4 hover:underline">
                        盯盘
                      </StockLink>
                    </td>
                    <td className={`num px-3 py-3 text-right ${priceTone(item.change_pct)}`}>{formatPrice(item.price)}</td>
                    <td className={`num px-3 py-3 text-right ${priceTone(item.change_pct)}`}>{formatPct(item.change_pct)}</td>
                    <td className="px-3 py-3 text-[#3c372f]">{item.latest_signal}</td>
                    <td className="px-4 py-3">
                      <Button size="sm" variant="ghost" onClick={() => void remove(item.code)}>
                        移出
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <ul className="space-y-3 md:hidden">
            {items.map((item) => (
              <li key={item.code}>
                <MobileRow item={item} onRemove={remove} />
              </li>
            ))}
          </ul>
        </>
      )}

      <ShockPad
        enabled={(data?.quote_source ?? meta?.quote_source) === "mock"}
        options={items.map((item) => ({ code: item.code, name: item.name }))}
        onDone={() => void load()}
      />
      <p className="text-xs leading-5 text-[#6f675c]">仅供研究参考，不构成投资建议。参考价取加入自选时的价格，止损按它来算。</p>
    </div>
  );
}

function MobileRow({ item, onRemove }: { item: WatchItem; onRemove: (code: string) => void }) {
  return (
    <article className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <StockLink code={item.code} name={item.name} className="font-medium">
            {item.name}
          </StockLink>
          <p className="num text-xs text-[#6f675c]">{item.code}</p>
        </div>
        <StatusPill level={item.status} label={item.status_label} />
      </div>
      <p className={`num mt-3 text-xl ${priceTone(item.change_pct)}`}>
        {formatPrice(item.price)} <span className="text-base">{formatPct(item.change_pct)}</span>
      </p>
      <p className="mt-2 text-sm text-[#3c372f]">{item.latest_signal}</p>
      <Button className="mt-3" size="sm" variant="ghost" onClick={() => onRemove(item.code)}>
        移出
      </Button>
    </article>
  );
}
