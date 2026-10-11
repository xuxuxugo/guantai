"use client";

import { useEffect, useState } from "react";
import { CodePicker, ErrorNote, LoadingBlock, Note, Spark } from "@/components/desk-ui";
import { useResearchCode } from "@/components/use-research-code";
import { Button } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { formatPct, formatPrice, formatYiYuan, priceTone } from "@/lib/format";
import { researchHref, useStock } from "@/lib/stock-context";
import type { AgentReport, BacktestResult, FinancialView, StockDetail, TechnicalView } from "@/lib/types";
import Link from "next/link";

export function StockInfo({ initialCode = "600519" }: { initialCode?: string }) {
  const { code, setCode } = useResearchCode(initialCode);
  const { setStock } = useStock();
  const [data, setData] = useState<StockDetail | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let stop = false;
    setLoading(true);
    api.stock(code).then((next) => {
      if (stop) return;
      setData(next);
      setError("");
      setStock(next.code, next.name);
    }).catch((err) => {
      if (!stop) setError(errorMessage(err, "个股没有取到"));
    }).finally(() => {
      if (!stop) setLoading(false);
    });
    return () => {
      stop = true;
    };
  }, [code, setStock]);

  return (
    <div className="space-y-5">
      <CodePicker code={code} onChange={setCode} compact />
      <ErrorNote text={error} />
      {loading && !data && <LoadingBlock />}
      {data && (
        <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <h2 className="font-serif text-2xl">{data.name}</h2>
              <p className="num text-sm text-[#6f675c]">{data.code}</p>
            </div>
            <div className="text-right">
              <p className={`num text-3xl ${priceTone(data.change_pct)}`}>{formatPrice(data.price)}</p>
              <p className={`num ${priceTone(data.change_pct)}`}>{formatPct(data.change_pct)}</p>
            </div>
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <Stat label="昨收" value={formatPrice(data.prev_close)} />
            <Stat label="今开" value={formatPrice(data.open)} />
            <Stat label="最高" value={formatPrice(data.high)} />
            <Stat label="最低" value={formatPrice(data.low)} />
            <Stat label="量比" value={data.volume_ratio.toFixed(2)} />
            <Stat label="20日高点" value={formatPrice(data.high_20d)} />
          </dl>
          <p className="mt-3 text-sm text-[#6f675c]">{data.session_label}{data.stale ? " · 行情延迟，显示上次成功报价" : ""}</p>
          <div className="mt-4">
            <Spark values={data.candles.map((item) => item.close)} />
            <p className="text-xs text-[#6f675c]">前复权日 K 收盘。更细的指标在技术分析。</p>
          </div>
          <div className="mt-3 flex flex-wrap gap-4 text-sm">
            <Link href={researchHref("/technical", data.code)} className="underline underline-offset-4">
              技术分析
            </Link>
            <Link href={researchHref("/financial", data.code)} className="underline underline-offset-4">
              财务分析
            </Link>
            <Link href={`/stocks/${data.code}`} className="underline underline-offset-4">
              盯盘详情
            </Link>
          </div>
        </section>
      )}
    </div>
  );
}

export function TechnicalDesk({ initialCode = "600519" }: { initialCode?: string }) {
  const { code, setCode } = useResearchCode(initialCode);
  const { setStock } = useStock();
  const [period, setPeriod] = useState<"day" | "week">("day");
  const [minute, setMinute] = useState(false);
  const [data, setData] = useState<TechnicalView | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let stop = false;
    setLoading(true);
    api.technical(code, period, minute).then((next) => {
      if (stop) return;
      setData(next);
      setError("");
      setStock(next.code, next.name);
    }).catch((err) => {
      if (!stop) setError(errorMessage(err, "技术指标没有取到"));
    }).finally(() => {
      if (!stop) setLoading(false);
    });
    return () => {
      stop = true;
    };
  }, [code, period, minute, setStock]);

  const latest = data?.latest;
  return (
    <div className="space-y-5">
      <CodePicker code={code} onChange={setCode} compact />
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant={period === "day" ? "default" : "outline"} onClick={() => setPeriod("day")}>日K</Button>
        <Button size="sm" variant={period === "week" ? "default" : "outline"} onClick={() => setPeriod("week")}>周K</Button>
        <Button size="sm" variant={minute ? "default" : "outline"} onClick={() => setMinute((value) => !value)}>分时</Button>
      </div>
      <ErrorNote text={error} />
      {loading && !data && <LoadingBlock />}
      {data && (
        <section className="space-y-4 rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <h2 className="font-medium">{data.name} · 综合评级 {data.rating.label}</h2>
            <span className="text-sm text-[#6f675c]">分数 {data.rating.score}</span>
          </div>
          <ul className="text-sm leading-6 text-[#3c372f]">
            {data.rating.reasons.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
          <Note text={data.note} />
          {latest && (
            <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
              <Stat label="收盘" value={formatPrice(latest.close)} />
              <Stat label="MACD" value={latest.hist == null ? "—" : latest.hist.toFixed(2)} />
              <Stat label="RSI" value={latest.rsi == null ? "—" : latest.rsi.toFixed(1)} />
              <Stat label="KDJ" value={latest.k == null ? "—" : `${latest.k.toFixed(0)}/${latest.d?.toFixed(0)}/${latest.j?.toFixed(0)}`} />
            </dl>
          )}
          <div>
            <p className="mb-1 text-xs text-[#6f675c]">收盘与布林中轨</p>
            <Spark values={data.series.map((item) => item.close)} />
          </div>
          <div>
            <p className="mb-1 text-xs text-[#6f675c]">MACD 柱</p>
            <Spark values={data.series.map((item) => item.hist).filter((item): item is number => item != null)} color="#1c1915" />
          </div>
          {minute && (
            <div>
              <p className="mb-1 text-xs text-[#6f675c]">分时</p>
              <Note text={data.minute_note} />
              <Spark values={data.minute.map((item) => item.price)} color="#a67c12" />
            </div>
          )}
          <p className="text-xs text-[#6f675c]">{data.disclaimer}</p>
        </section>
      )}
    </div>
  );
}

export function FinancialDesk({ initialCode = "600519" }: { initialCode?: string }) {
  const { code, setCode } = useResearchCode(initialCode);
  const { setStock } = useStock();
  const [data, setData] = useState<FinancialView | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let stop = false;
    setLoading(true);
    api.financials(code).then((next) => {
      if (stop) return;
      setData(next);
      setError("");
      setStock(next.code, next.name);
    }).catch((err) => {
      if (!stop) setError(errorMessage(err, "财务数据没有取到"));
    }).finally(() => {
      if (!stop) setLoading(false);
    });
    return () => {
      stop = true;
    };
  }, [code, setStock]);

  return (
    <div className="space-y-5">
      <CodePicker code={code} onChange={setCode} compact />
      <ErrorNote text={error} />
      {loading && !data && <LoadingBlock />}
      {data && (
        <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
          <h2 className="font-medium">{data.name} · {data.source}</h2>
          <Note text={data.note || (data.stale ? "财务延迟，显示上次成功结果。" : "")} />
          {data.rows.length === 0 ? (
            <p className="mt-3 text-sm text-[#6f675c]">暂时没有财务行。接口失败时不会编造数字。</p>
          ) : (
            <div className="mt-3 overflow-x-auto">
              <table className="w-full min-w-[720px] text-sm">
                <thead className="text-left text-xs text-[#6f675c]">
                  <tr>
                    <th className="py-2">报告期</th>
                    <th>营收</th>
                    <th>归母净利</th>
                    <th>营收同比</th>
                    <th>净利同比</th>
                    <th>ROE</th>
                    <th>毛利率</th>
                    <th>资产负债率</th>
                    <th>EPS</th>
                  </tr>
                </thead>
                <tbody>
                  {data.rows.map((row) => (
                    <tr key={row.period} className="border-t border-[#eee6d8]">
                      <td className="py-2">{row.period}</td>
                      <td className="num">{formatYiYuan(row.revenue)}</td>
                      <td className="num">{formatYiYuan(row.profit)}</td>
                      <td className="num">{row.revenue_yoy == null ? "—" : formatPct(row.revenue_yoy)}</td>
                      <td className="num">{row.profit_yoy == null ? "—" : formatPct(row.profit_yoy)}</td>
                      <td className="num">{row.roe == null ? "—" : `${row.roe.toFixed(2)}%`}</td>
                      <td className="num">{row.gross_margin == null ? "—" : `${row.gross_margin.toFixed(1)}%`}</td>
                      <td className="num">{row.debt_ratio == null ? "—" : `${row.debt_ratio.toFixed(1)}%`}</td>
                      <td className="num">{row.eps == null ? "—" : row.eps.toFixed(2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="mt-3 text-xs text-[#6f675c]">{data.disclaimer}</p>
        </section>
      )}
    </div>
  );
}

export function QuantDesk({ initialCode = "600519" }: { initialCode?: string }) {
  const { code, setCode } = useResearchCode(initialCode);
  const { setStock } = useStock();
  const [strategy, setStrategy] = useState("momentum");
  const [data, setData] = useState<BacktestResult | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let stop = false;
    setLoading(true);
    api.backtest(code, strategy).then((next) => {
      if (stop) return;
      setData(next);
      setError("");
      setStock(next.code, next.name);
    }).catch((err) => {
      if (!stop) setError(errorMessage(err, "回测没有跑完"));
    }).finally(() => {
      if (!stop) setLoading(false);
    });
    return () => {
      stop = true;
    };
  }, [code, strategy, setStock]);

  return (
    <div className="space-y-5">
      <CodePicker code={code} onChange={setCode} compact />
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant={strategy === "momentum" ? "default" : "outline"} onClick={() => setStrategy("momentum")}>动量</Button>
        <Button size="sm" variant={strategy === "mean_reversion" ? "default" : "outline"} onClick={() => setStrategy("mean_reversion")}>高抛低吸</Button>
      </div>
      <ErrorNote text={error} />
      {loading && !data && <LoadingBlock label="正在用日K回测" />}
      {data && (
        <section className="space-y-3 rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
          <h2 className="font-medium">{data.name} · {data.title}</h2>
          <dl className="grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
            <Stat label="区间收益" value={formatPct(data.total_return_pct)} />
            <Stat label="最大回撤" value={`${data.max_drawdown_pct.toFixed(2)}%`} />
            <Stat label="卖出胜率" value={`${data.win_rate_pct.toFixed(0)}%`} />
            <Stat label="交易次数" value={String(data.trade_count)} />
          </dl>
          <p className="text-xs text-[#6f675c]">净值（起点 1）</p>
          <Spark values={data.equity.map((item) => item.equity)} color="#1c1915" />
          <p className="text-xs text-[#6f675c]">回撤（%）</p>
          <Spark values={drawdowns(data.equity.map((item) => item.equity))} color="#1d7a4a" />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-left text-xs text-[#6f675c]">
                <tr><th>日期</th><th>方向</th><th>价格</th><th>盈亏</th></tr>
              </thead>
              <tbody>
                {data.trades.slice(-12).map((trade, index) => (
                  <tr key={`${trade.date}-${trade.side}-${index}`} className="border-t border-[#eee6d8]">
                    <td className="py-2">{trade.date}</td>
                    <td>{trade.side}</td>
                    <td className="num">{formatPrice(trade.price)}</td>
                    <td className="num">{trade.pnl_pct == null ? "—" : formatPct(trade.pnl_pct)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Note text={data.note} />
        </section>
      )}
    </div>
  );
}

export function AgentDesk({ initialCode = "600519" }: { initialCode?: string }) {
  const { code, setCode } = useResearchCode(initialCode);
  const [question, setQuestion] = useState("");
  const [data, setData] = useState<AgentReport | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function run() {
    setLoading(true);
    setError("");
    try {
      setData(await api.agent(code, question));
    } catch (err) {
      setError(errorMessage(err, "报告没有生成"));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void run();
    // regenerate when the shared research code changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code]);

  return (
    <div className="space-y-5">
      <CodePicker code={code} onChange={setCode} compact />
      <label className="block text-sm text-[#6f675c]">
        想看的问题（可选）
        <textarea
          className="mt-1 min-h-20 w-full rounded-md border border-[#d9d0c1] bg-white px-3 py-2 text-[#1c1915]"
          value={question}
          maxLength={200}
          onChange={(event) => setQuestion(event.target.value)}
        />
      </label>
      <Button onClick={() => void run()} disabled={loading}>{loading ? "生成中…" : "生成报告"}</Button>
      <ErrorNote text={error} />
      {loading && !data && <LoadingBlock label="正在整理多角色笔记" />}
      {data && (
        <section className="space-y-3">
          <p className="text-sm text-[#6f675c]">{data.demo ? "演示报告" : "模型报告"} · {data.source}</p>
          <Note text={data.note} />
          {data.roles.map((role) => (
            <article key={role.role} className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
              <h2 className="font-medium">{role.role}</h2>
              <p className="mt-2 text-sm leading-7 text-[#3c372f]">{role.text}</p>
            </article>
          ))}
          <p className="text-xs text-[#6f675c]">{data.disclaimer}</p>
        </section>
      )}
    </div>
  );
}

function drawdowns(equity: number[]) {
  let peak = equity[0] ?? 1;
  return equity.map((value) => {
    peak = Math.max(peak, value);
    return peak <= 0 ? 0 : (value / peak - 1) * 100;
  });
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-[#f7f1e6] px-3 py-2">
      <dt className="text-xs text-[#6f675c]">{label}</dt>
      <dd className="num mt-1">{value}</dd>
    </div>
  );
}
