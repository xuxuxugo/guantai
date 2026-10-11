"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { ErrorNote, LoadingBlock, Note } from "@/components/desk-ui";
import { StockLink } from "@/components/stock-link";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useLive } from "@/components/shell";
import { api, errorMessage } from "@/lib/api";
import { formatCapYi, formatPct, formatPrice, formatTurnover, priceTone } from "@/lib/format";
import type {
  CalendarView,
  DataCenterView,
  DigestView,
  MarketOverview,
  NewsFeed,
  OpportunityView,
  PoolSnapshot,
  RankingsResult,
  Rules,
  ScreenResult,
  WatchlistResponse,
} from "@/lib/types";

function heat(change: number) {
  if (change >= 2) return "#9d3428";
  if (change > 0) return "#c24532";
  if (change <= -2) return "#17653d";
  if (change < 0) return "#1d7a4a";
  return "#6f675c";
}

function RankList({ title, rows, field }: { title: string; rows: PoolSnapshot["rows"]; field: "change" | "turnover" }) {
  return (
    <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
      <h2 className="font-medium">{title}</h2>
      {rows.length === 0 && <p className="mt-3 text-sm text-[#6f675c]">这一栏暂时没有报价。</p>}
      <ul className="mt-2 divide-y divide-[#eee6d8]">
        {rows.map((row) => (
          <li key={row.code} className="flex items-center justify-between gap-3 py-2 text-sm">
            <StockLink code={row.code} name={row.name} className="underline-offset-4 hover:underline">
              {row.name}
            </StockLink>
            <span className={`num ${field === "change" ? priceTone(row.change_pct) : ""}`}>
              {field === "change" ? formatPct(row.change_pct) : formatTurnover(row.turnover)}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ScreenDesk() {
  const [minChange, setMinChange] = useState("");
  const [maxChange, setMaxChange] = useState("");
  const [minRatio, setMinRatio] = useState("");
  const [minTurnover, setMinTurnover] = useState("");
  const [minCap, setMinCap] = useState("");
  const [data, setData] = useState<ScreenResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (query: string) => {
    setLoading(true);
    try {
      setData(await api.screen(query));
      setError("");
    } catch (err) {
      setError(errorMessage(err, "选股没有完成"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load("");
  }, [load]);

  function queryFromForm() {
    const params = new URLSearchParams();
    if (minChange.trim()) params.set("min_change", minChange.trim());
    if (maxChange.trim()) params.set("max_change", maxChange.trim());
    if (minRatio.trim()) params.set("min_volume_ratio", minRatio.trim());
    if (minTurnover.trim()) params.set("min_turnover", String(Number(minTurnover) * 100000000));
    if (minCap.trim()) params.set("min_market_cap", minCap.trim());
    const query = params.toString();
    return query ? `?${query}` : "";
  }

  return (
    <div className="space-y-5">
      <form
        className="grid gap-3 rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4 sm:grid-cols-2 lg:grid-cols-3"
        onSubmit={(event) => {
          event.preventDefault();
          void load(queryFromForm());
        }}
      >
        <label className="text-sm text-[#6f675c]">
          涨跌幅下限 %
          <Input className="mt-1" inputMode="decimal" value={minChange} onChange={(event) => setMinChange(event.target.value)} />
        </label>
        <label className="text-sm text-[#6f675c]">
          涨跌幅上限 %
          <Input className="mt-1" inputMode="decimal" value={maxChange} onChange={(event) => setMaxChange(event.target.value)} />
        </label>
        <label className="text-sm text-[#6f675c]">
          量比下限
          <Input className="mt-1" inputMode="decimal" value={minRatio} onChange={(event) => setMinRatio(event.target.value)} />
        </label>
        <label className="text-sm text-[#6f675c]">
          成交额下限（亿元）
          <Input className="mt-1" inputMode="decimal" value={minTurnover} onChange={(event) => setMinTurnover(event.target.value)} />
        </label>
        <label className="text-sm text-[#6f675c]">
          市值下限（亿元）
          <Input className="mt-1" inputMode="decimal" value={minCap} onChange={(event) => setMinCap(event.target.value)} />
        </label>
        <div className="flex items-end">
          <Button type="submit" disabled={loading}>{loading ? "筛选中…" : "筛选"}</Button>
        </div>
      </form>
      <ErrorNote text={error} />
      {loading && !data && <LoadingBlock label="正在筛热门池" />}
      {data && (
        <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
          <p className="text-sm text-[#6f675c]">热门池 {data.pool_size} 只，命中 {data.rows.length} 只。{data.stale ? "行情延迟。" : ""}</p>
          <Note text={data.note} />
          {data.rows.length === 0 ? (
            <p className="mt-3 text-sm text-[#6f675c]">没有符合条件的股票。放宽条件，或等报价回来再筛。</p>
          ) : (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[640px] text-sm">
                <thead className="text-left text-xs text-[#6f675c]">
                  <tr>
                    <th className="py-2">名称</th>
                    <th>板块</th>
                    <th>现价</th>
                    <th>涨跌幅</th>
                    <th>量比</th>
                    <th>成交额</th>
                    <th>市值</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((row) => (
                    <tr key={row.code} className="border-t border-[#eee6d8]">
                      <td className="py-2">
                        <StockLink code={row.code} name={row.name} className="underline-offset-4 hover:underline">{row.name}</StockLink>
                      </td>
                      <td>{row.sector}</td>
                      <td className="num">{formatPrice(row.price)}</td>
                      <td className={`num ${priceTone(row.change_pct)}`}>{formatPct(row.change_pct)}</td>
                      <td className="num">{row.volume_ratio.toFixed(2)}</td>
                      <td className="num">{formatTurnover(row.turnover)}</td>
                      <td className="num">{formatCapYi(row.market_cap)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
    </div>
  );
}

export function DigestDesk() {
  const [data, setData] = useState<DigestView | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let stop = false;
    api.digest().then((next) => {
      if (stop) return;
      setData(next);
    }).catch((err) => {
      if (!stop) setError(errorMessage(err, "日报没有生成"));
    }).finally(() => {
      if (!stop) setLoading(false);
    });
    return () => {
      stop = true;
    };
  }, []);

  return (
    <div className="space-y-5">
      <ErrorNote text={error} />
      {loading && !data && <LoadingBlock label="正在拼当日摘要" />}
      {data && (
        <>
          <p className="text-sm text-[#6f675c]">{data.session_label}{data.stale ? " · 部分行情延迟" : ""}</p>
          <Note text={data.note} />
          <ul className="grid gap-3 sm:grid-cols-3">
            {data.indices.map((item) => (
              <li key={item.symbol} className="rounded-xl border border-[#e0d8c8] bg-[#1c1915] p-4 text-[#f3efe6]">
                <p className="text-sm text-[#cfc6b6]">{item.name}</p>
                <p className="num mt-1 text-2xl">{formatPrice(item.price)}</p>
                <p className={`num text-sm ${item.change_pct >= 0 ? "text-[#ffb4a8]" : "text-[#8fd4ae]"}`}>{formatPct(item.change_pct)}</p>
              </li>
            ))}
          </ul>
          <div className="grid gap-3 lg:grid-cols-3">
            <RankList title="涨幅靠前" rows={data.leaders.gainers} field="change" />
            <RankList title="跌幅靠前" rows={data.leaders.losers} field="change" />
            <RankList title="成交额靠前" rows={data.leaders.turnover} field="turnover" />
          </div>
          <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
            <h2 className="font-medium">自选规则扫描</h2>
            {data.watch.length === 0 && <p className="mt-3 text-sm text-[#6f675c]">自选还是空的，盯盘台里加上股票后这里会有信号。</p>}
            <ul className="mt-2 divide-y divide-[#eee6d8]">
              {data.watch.map((item) => (
                <li key={item.code} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                  <StockLink code={item.code} name={item.name} className="font-medium underline-offset-4 hover:underline">{item.name}</StockLink>
                  <span className={priceTone(item.change_pct)}>{formatPct(item.change_pct)}</span>
                  <span>{item.status_label}</span>
                  <span className="text-[#6f675c]">{item.latest_signal}</span>
                </li>
              ))}
            </ul>
          </section>
          <p className="text-xs text-[#6f675c]">{data.disclaimer}</p>
        </>
      )}
    </div>
  );
}

export function OverviewDesk() {
  const [market, setMarket] = useState<MarketOverview | null>(null);
  const [board, setBoard] = useState<RankingsResult | null>(null);
  const [pool, setPool] = useState<PoolSnapshot | null>(null);
  const [news, setNews] = useState<NewsFeed | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let stop = false;
    Promise.allSettled([api.market(), api.rankings(), api.pool(), api.news("stock")]).then(([marketResult, rankResult, poolResult, newsResult]) => {
      if (stop) return;
      if (marketResult.status === "fulfilled") setMarket(marketResult.value);
      if (rankResult.status === "fulfilled") setBoard(rankResult.value);
      if (poolResult.status === "fulfilled") setPool(poolResult.value);
      if (newsResult.status === "fulfilled") setNews(newsResult.value);
      const failed = [rankResult, poolResult].find((item) => item.status === "rejected");
      setError(failed && failed.status === "rejected" ? errorMessage(failed.reason, "市场概览没有取全") : "");
      setLoading(false);
    });
    return () => {
      stop = true;
    };
  }, []);

  const breadth = market?.breadth;

  return (
    <div className="space-y-5">
      <ErrorNote text={error} />
      {loading && !board && <LoadingBlock />}
      {breadth && (
        <section className="rounded-xl border border-[#e0d8c8] bg-[#1c1915] p-4 text-[#f3efe6]">
          <h2 className="font-medium">涨跌家数</h2>
          {breadth.total > 0 ? (
            <p className="num mt-2 text-sm">
              <span className="text-[#ffb4a8]">上涨 {breadth.up}</span>
              <span className="mx-2 text-[#cfc6b6]">/</span>
              <span className="text-[#8fd4ae]">下跌 {breadth.down}</span>
              <span className="mx-2 text-[#cfc6b6]">/</span>
              <span className="text-[#cfc6b6]">平盘 {breadth.flat}</span>
            </p>
          ) : (
            <p className="mt-2 text-sm text-[#cfc6b6]">{breadth.note || "涨跌家数暂时不可用。"}</p>
          )}
          <p className="mt-2 text-xs text-[#cfc6b6]">{breadth.source}{breadth.stale ? " · 延迟" : ""}{breadth.note ? ` · ${breadth.note}` : ""}</p>
        </section>
      )}
      {board && (
        <>
          <Note text={board.note} />
          <div className="flex flex-wrap gap-2">
            {board.sectors.map((item) => (
              <span key={item.sector} className={`rounded-full bg-[#fbf8f2] px-3 py-1 text-sm ${priceTone(item.change_pct)}`}>
                {item.sector} {formatPct(item.change_pct)}
              </span>
            ))}
          </div>
          <div className="grid gap-3 lg:grid-cols-3">
            <RankList title="涨幅榜" rows={board.rankings.gainers} field="change" />
            <RankList title="跌幅榜" rows={board.rankings.losers} field="change" />
            <RankList title="成交额榜" rows={board.rankings.turnover} field="turnover" />
          </div>
        </>
      )}
      {pool && (
        <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
          <h2 className="font-medium">热图</h2>
          <ul className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-6">
            {pool.rows.filter((row) => row.price > 0).map((row) => (
              <li key={row.code}>
                <StockLink code={row.code} name={row.name} className="block rounded-lg px-2 py-3 text-center text-white transition-transform hover:scale-[1.02]" style={{ background: heat(row.change_pct) }}>
                  <p className="truncate text-sm">{row.name}</p>
                  <p className="num mt-1 text-sm">{formatPct(row.change_pct)}</p>
                </StockLink>
              </li>
            ))}
          </ul>
        </section>
      )}
      {news && (
        <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
          <div className="flex items-baseline justify-between gap-3">
            <h2 className="font-medium">股市快讯</h2>
            <Link href="/news" className="text-sm text-[#6f675c] underline-offset-4 hover:underline">全部新闻</Link>
          </div>
          <Note text={news.note || news.source} />
          <ul className="mt-2 space-y-2">
            {news.items.slice(0, 5).map((item) => (
              <li key={item.url || item.title} className="text-sm">
                <a href={item.url} target="_blank" rel="noreferrer" className="underline-offset-4 hover:underline">{item.title}</a>
                <span className="ml-2 text-xs text-[#6f675c]">{item.published_at}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}

function csvCell(value: string | number) {
  return `"${String(value).replaceAll('"', '""')}"`;
}

function downloadCsv(filename: string, rows: (string | number)[][]) {
  const text = rows.map((row) => row.map(csvCell).join(",")).join("\n");
  const blob = new Blob([`\ufeff${text}`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export function DataDesk() {
  const [data, setData] = useState<DataCenterView | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let stop = false;
    api.datacenter().then((next) => {
      if (stop) return;
      setData(next);
    }).catch((err) => {
      if (!stop) setError(errorMessage(err, "数据中心没有打开"));
    }).finally(() => {
      if (!stop) setLoading(false);
    });
    return () => {
      stop = true;
    };
  }, []);

  return (
    <div className="space-y-5">
      <ErrorNote text={error} />
      {loading && !data && <LoadingBlock />}
      {data && (
        <>
          <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4 text-sm leading-6">
            <p>行情源 {data.quote_source} · {data.market_name}</p>
            <p>{data.session_label}{data.index_stale || data.pool_stale ? " · 有缓存延迟" : " · 缓存可用"}</p>
            <Note text={data.note} />
            <Button
              className="mt-3"
              onClick={() => {
                const rows: (string | number)[][] = [["类型", "代码", "名称", "价格", "涨跌幅", "量比或成交额"]];
                data.indices.forEach((item) => rows.push(["指数", item.code, item.name, item.price, item.change_pct, item.turnover]));
                data.watchlist.forEach((item) => rows.push(["自选", item.code, item.name, item.price, item.change_pct, item.volume_ratio]));
                data.pool.forEach((item) => rows.push(["热门池", item.code, item.name, item.price, item.change_pct, item.turnover]));
                downloadCsv("guanlan-quotes.csv", rows);
              }}
            >
              导出 CSV
            </Button>
          </section>
          <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
            <h2 className="font-medium">指数</h2>
            <ul className="mt-2 divide-y divide-[#eee6d8]">
              {data.indices.map((item) => (
                <li key={item.symbol} className="flex items-center justify-between gap-3 py-2 text-sm">
                  <span>{item.name}{item.stale ? " · 延迟" : ""}</span>
                  <span className={`num ${priceTone(item.change_pct)}`}>{formatPrice(item.price)} {formatPct(item.change_pct)}</span>
                </li>
              ))}
            </ul>
          </section>
          <section className="overflow-x-auto rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
            <h2 className="font-medium">自选行情</h2>
            {data.watchlist.length === 0 && <p className="mt-3 text-sm text-[#6f675c]">自选是空的。</p>}
            <table className="mt-2 w-full min-w-[480px] text-sm">
              <thead className="text-left text-xs text-[#6f675c]">
                <tr><th className="py-2">名称</th><th>价格</th><th>涨跌幅</th><th>量比</th></tr>
              </thead>
              <tbody>
                {data.watchlist.map((item) => (
                  <tr key={item.code} className="border-t border-[#eee6d8]">
                    <td className="py-2">{item.name}{item.stale ? " · 延迟" : ""}</td>
                    <td className="num">{formatPrice(item.price)}</td>
                    <td className={`num ${priceTone(item.change_pct)}`}>{formatPct(item.change_pct)}</td>
                    <td className="num">{item.volume_ratio.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </section>
        </>
      )}
    </div>
  );
}

export function CalendarDesk() {
  const [data, setData] = useState<CalendarView | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let stop = false;
    api.calendar().then((next) => {
      if (stop) return;
      setData(next);
    }).catch((err) => {
      if (!stop) setError(errorMessage(err, "日历没有打开"));
    }).finally(() => {
      if (!stop) setLoading(false);
    });
    return () => {
      stop = true;
    };
  }, []);

  return (
    <div className="space-y-5">
      <ErrorNote text={error} />
      {loading && !data && <LoadingBlock />}
      {data && (
        <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
          <p className="inline-block rounded-full bg-[#f7e7e2] px-3 py-1 text-sm text-[#8d3428]">{data.source}</p>
          <p className="mt-3 text-sm leading-6 text-[#3c372f]">{data.note}</p>
          <ul className="mt-4 divide-y divide-[#eee6d8]">
            {data.events.map((item) => (
              <li key={`${item.date}-${item.title}`} className="flex flex-wrap items-baseline justify-between gap-2 py-3 text-sm">
                <span className="num text-[#6f675c]">{item.date}</span>
                <span className="min-w-0 flex-1">{item.region} · {item.title}</span>
                <span className="text-[#6f675c]">{item.importance}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-xs text-[#6f675c]">{data.disclaimer}</p>
        </section>
      )}
    </div>
  );
}

export function NewsDesk() {
  const [column, setColumn] = useState("headline");
  const [data, setData] = useState<NewsFeed | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const load = useCallback(async (nextColumn: string) => {
    setLoading(true);
    try {
      setData(await api.news(nextColumn));
      setError("");
    } catch (err) {
      setError(errorMessage(err, "新闻没有刷新"));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(column);
  }, [column, load]);

  const columns = data?.columns?.length ? data.columns : [
    { id: "headline", label: "要闻" },
    { id: "stock", label: "股市" },
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-2">
        {columns.map((item) => (
          <Button key={item.id} size="sm" variant={column === item.id ? "default" : "outline"} onClick={() => setColumn(item.id)}>
            {item.label}
          </Button>
        ))}
        <Button size="sm" variant="outline" onClick={() => void load(column)} disabled={loading}>刷新</Button>
      </div>
      <ErrorNote text={error} />
      {loading && !data && <LoadingBlock label="正在拉新闻" />}
      {data && (
        <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
          <p className="text-sm text-[#6f675c]">{data.source}{data.stale ? " · 显示上次成功结果" : ""}</p>
          <Note text={data.note} />
          {data.items.length === 0 ? (
            <p className="mt-3 text-sm text-[#6f675c]">这一栏暂时没有条目。</p>
          ) : (
            <ul className="mt-3 divide-y divide-[#eee6d8]">
              {data.items.map((item) => (
                <li key={`${item.published_at}-${item.title}`} className="py-3">
                  <a href={item.url || undefined} target="_blank" rel="noreferrer" className="font-medium underline-offset-4 hover:underline">
                    {item.title}
                  </a>
                  <p className="mt-1 text-xs text-[#6f675c]">{item.source} · {item.published_at}</p>
                  {item.summary && <p className="mt-1 text-sm leading-6 text-[#3c372f]">{item.summary}</p>}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
    </div>
  );
}

export function OpportunityDesk() {
  const [data, setData] = useState<OpportunityView | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let stop = false;
    api.opportunities().then((next) => {
      if (stop) return;
      setData(next);
    }).catch((err) => {
      if (!stop) setError(errorMessage(err, "机会跟踪没有打开"));
    }).finally(() => {
      if (!stop) setLoading(false);
    });
    return () => {
      stop = true;
    };
  }, []);

  return (
    <div className="space-y-5">
      <ErrorNote text={error} />
      {loading && !data && <LoadingBlock />}
      {data && (
        <>
          <section className="rounded-xl border border-[#e0d8c8] bg-[#1c1915] p-4 text-[#f3efe6]">
            <p className="text-sm text-[#cfc6b6]">{data.vix.name} · {data.vix.source || "公开行情"}</p>
            <p className="num mt-2 text-3xl">{data.vix.price > 0 ? data.vix.price.toFixed(2) : "—"}</p>
            <p className="num text-sm text-[#ffb4a8]">{formatPct(data.vix.change_pct)}{data.vix.stale ? " · 延迟或未取到" : ""}</p>
            <Note text={data.vix.note} />
          </section>
          <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
            <h2 className="font-medium">自选相关信号</h2>
            {data.signals.length === 0 && <p className="mt-3 text-sm text-[#6f675c]">自选是空的，信号列表会跟着盯盘台走。</p>}
            <ul className="mt-2 divide-y divide-[#eee6d8]">
              {data.signals.map((item) => (
                <li key={item.code} className="flex flex-wrap items-center justify-between gap-2 py-2 text-sm">
                  <StockLink code={item.code} name={item.name} className="underline-offset-4 hover:underline">{item.name}</StockLink>
                  <span>{item.status_label}</span>
                  <span className="text-[#6f675c]">{item.latest_signal}</span>
                </li>
              ))}
            </ul>
          </section>
          <div className="grid gap-3 sm:grid-cols-2">
            {data.unavailable.map((item) => (
              <section key={item.name} className="rounded-xl border border-dashed border-[#d9d0c1] bg-[#fbf8f2] p-4">
                <h2 className="font-medium">{item.name}</h2>
                <p className="mt-2 text-sm leading-6 text-[#6f675c]">{item.note}</p>
              </section>
            ))}
          </div>
          <p className="text-xs text-[#6f675c]">{data.disclaimer}</p>
        </>
      )}
    </div>
  );
}

export function MeDesk() {
  const { meta } = useLive();
  const [watch, setWatch] = useState<WatchlistResponse | null>(null);
  const [rules, setRules] = useState<Rules | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let stop = false;
    Promise.allSettled([api.watchlist(), api.rules()]).then(([watchResult, ruleResult]) => {
      if (stop) return;
      if (watchResult.status === "fulfilled") setWatch(watchResult.value);
      if (ruleResult.status === "fulfilled") setRules(ruleResult.value);
      const failed = [watchResult, ruleResult].find((item) => item.status === "rejected");
      setError(failed && failed.status === "rejected" ? errorMessage(failed.reason, "本地资料没有取全") : "");
    });
    return () => {
      stop = true;
    };
  }, []);

  const switches = rules
    ? [
        ["突破 20 日高点", rules.breakout_20d_enabled],
        ["短窗口涨跌", rules.swing_enabled],
        ["止损", rules.stop_loss_enabled],
        ["量比突增", rules.volume_spike_enabled],
        ["仅交易时段出警", rules.trading_hours_only],
      ]
    : [];

  return (
    <div className="space-y-5">
      <ErrorNote text={error} />
      <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
        <h2 className="font-medium">本地账户</h2>
        <p className="mt-2 text-sm leading-6">演示用户 {meta?.demo_user || "demo"}。没有密码，也没有会员和邀请码。自选、规则和告警都挂在这个用户上。</p>
        <p className="mt-2 text-sm text-[#6f675c]">自选 {watch ? watch.items.length : "…"} 只</p>
        <div className="mt-3 flex flex-wrap gap-4 text-sm">
          <Link href="/watch" className="underline underline-offset-4">管理自选</Link>
          <Link href="/rules" className="underline underline-offset-4">修改规则</Link>
        </div>
      </section>
      <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4 text-sm leading-7">
        <h2 className="font-medium">设置</h2>
        <p>行情源 {meta?.quote_source || "tencent"} · {meta?.market || "腾讯行情"}</p>
        <p>交易时段刷新 {meta?.scan_interval_seconds ?? 4} 秒，非交易时段 {meta?.offhours_scan_interval_seconds ?? 60} 秒</p>
        <p>{meta?.session_label || "时段待确认"}</p>
        <ul className="mt-2">
          {switches.map(([label, on]) => (
            <li key={String(label)}>{label}：{on ? "开" : "关"}</li>
          ))}
        </ul>
      </section>
    </div>
  );
}
