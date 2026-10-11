"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { CandleChart } from "@/components/candle-chart";
import { useLive } from "@/components/shell";
import { ShockPad } from "@/components/shock-pad";
import { StatusPill } from "@/components/status-pill";
import { StockLink } from "@/components/stock-link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, errorMessage } from "@/lib/api";
import { formatPct, formatPrice, priceTone } from "@/lib/format";
import { researchHref, useStock } from "@/lib/stock-context";
import type { StockDetail as StockData } from "@/lib/types";

export function StockDetail({ code }: { code: string }) {
  const { revision, meta } = useLive();
  const { setStock } = useStock();
  const [data, setData] = useState<StockData | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [stop, setStop] = useState("");
  const [busy, setBusy] = useState("");
  const [note, setNote] = useState("");
  const loadedFor = useRef("");

  useEffect(() => {
    if (!/^\d{6}$/.test(code)) {
      setLoading(false);
      setError("演示行情里没有这只股票");
      return;
    }
    let stopPolling = false;
    async function load() {
      try {
        const next = await api.stock(code);
        if (stopPolling) return;
        setData(next);
        setError("");
        setStock(next.code, next.name);
        if (loadedFor.current !== next.code) {
          loadedFor.current = next.code;
          setStop(next.stop_loss_pct == null ? "" : String(next.stop_loss_pct));
        }
      } catch (err) {
        if (!stopPolling) setError(errorMessage(err, "个股详情暂时没有取到"));
      } finally {
        if (!stopPolling) setLoading(false);
      }
    }
    void load();
    const timer = window.setInterval(() => void load(), 4000);
    return () => {
      stopPolling = true;
      window.clearInterval(timer);
    };
  }, [code, revision, setStock]);

  async function toggleWatch() {
    if (!data) return;
    setBusy("watch");
    setNote("");
    try {
      if (data.in_watchlist) {
        await api.removeWatch(data.code);
        setNote("已移出盯盘台");
      } else {
        await api.addWatch(data.code);
        setNote("已加入盯盘台");
        loadedFor.current = "";
      }
      const next = await api.stock(data.code);
      setData(next);
      if (next.stop_loss_pct != null) setStop(String(next.stop_loss_pct));
    } catch (err) {
      setNote(errorMessage(err, "自选没有更新"));
    } finally {
      setBusy("");
    }
  }

  async function saveStop() {
    if (!data) return;
    const value = Number(stop);
    if (!Number.isFinite(value)) {
      setNote("止损要填成数字");
      return;
    }
    setBusy("stop");
    setNote("");
    try {
      const saved = await api.patchWatch(data.code, { stop_loss_pct: value });
      setStop(String(saved.stop_loss_pct));
      setNote(`止损已设为 ${saved.stop_loss_pct}%`);
      const next = await api.stock(data.code);
      setData(next);
    } catch (err) {
      setNote(errorMessage(err, "止损没有保存"));
    } finally {
      setBusy("");
    }
  }

  async function resetRef() {
    if (!data) return;
    setBusy("ref");
    setNote("");
    try {
      const saved = await api.patchWatch(data.code, { reset_ref: true });
      setNote(`参考价已改为现价 ${saved.ref_price.toFixed(2)}`);
      const next = await api.stock(data.code);
      setData(next);
    } catch (err) {
      setNote(errorMessage(err, "参考价没有更新"));
    } finally {
      setBusy("");
    }
  }

  if (loading && !data) {
    return <div className="h-64 animate-pulse rounded-xl bg-[#e7e1d6]" aria-busy="true" />;
  }
  if (error && !data) {
    return (
      <div className="rounded-xl border border-dashed border-[#d9d0c1] bg-[#fbf8f2] px-4 py-10 text-center">
        <p className="font-medium">{error}</p>
        <Link href="/watch" className="mt-3 inline-block text-sm underline underline-offset-4">
          返回盯盘台
        </Link>
      </div>
    );
  }
  if (!data) return null;

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap gap-4 text-sm">
        <Link href="/watch" className="text-[#6f675c] underline-offset-4 hover:underline">
          返回盯盘台
        </Link>
        <StockLink code={data.code} name={data.name} href={researchHref("/info", data.code)} className="underline underline-offset-4">
          个股信息
        </StockLink>
        <StockLink code={data.code} name={data.name} href={researchHref("/technical", data.code)} className="underline underline-offset-4">
          技术分析
        </StockLink>
        <StockLink code={data.code} name={data.name} href={researchHref("/financial", data.code)} className="underline underline-offset-4">
          财务分析
        </StockLink>
      </div>
      <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-serif text-3xl">{data.name}</h2>
              <span className="num text-sm text-[#6f675c]">{data.code}</span>
              <Badge>{(data.quote_source ?? meta?.quote_source) === "mock" ? "模拟行情" : "腾讯行情"}</Badge>
              {data.session_label && <span className="text-xs text-[#6f675c]">{data.session_label}</span>}
              {data.stale && <span className="text-xs text-[#8d3428]">行情延迟，显示上次成功报价</span>}
            </div>
            <div className="mt-2">
              <StatusPill level={data.status} label={data.status_label} />
            </div>
          </div>
          <div className="text-right">
            <p className={`num text-3xl ${priceTone(data.change_pct)}`}>{formatPrice(data.price)}</p>
            <p className={`num text-sm ${priceTone(data.change_pct)}`}>{formatPct(data.change_pct)}</p>
          </div>
        </div>
        <dl className="mt-5 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
          <Stat label="昨收" value={formatPrice(data.prev_close)} />
          <Stat label="今开" value={formatPrice(data.open)} />
          <Stat label="最高" value={formatPrice(data.high)} />
          <Stat label="最低" value={formatPrice(data.low)} />
          <Stat label="量比" value={data.volume_ratio.toFixed(2)} />
          <Stat label="20日高点" value={formatPrice(data.high_20d)} />
          <Stat label="参考价" value={data.ref_price == null ? "—" : formatPrice(data.ref_price)} />
          <Stat label="止损" value={data.stop_loss_pct == null ? "—" : `${data.stop_loss_pct}%`} />
        </dl>
        <p className="mt-4 text-xs text-[#6f675c]">
          {data.disclaimer}。下图是{(data.quote_source ?? meta?.quote_source) === "mock" ? "模拟 K 线" : "前复权日 K"}，红涨绿跌。
        </p>
      </section>

      <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
        <h3 className="mb-2 text-sm text-[#6f675c]">近 40 个交易日</h3>
        <CandleChart
          candles={data.candles}
          label={(data.quote_source ?? meta?.quote_source) === "mock" ? "近40个交易日模拟K线" : "近40个交易日前复权K线"}
        />
      </section>

      <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-5">
        <h3 className="font-medium">触发原因</h3>
        <ul className="mt-3 divide-y divide-[#eee6d8]">
          {data.triggers.map((trigger) => (
            <li key={trigger.rule_key} className="flex flex-col gap-1 py-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="font-medium">{trigger.title}</p>
                <p className="text-sm leading-6 text-[#3c372f]">{trigger.detail}</p>
              </div>
              <span className="shrink-0 text-sm text-[#6f675c]">
                {!trigger.enabled ? "未开启" : trigger.hit ? "已触发" : trigger.level === "observe" ? "接近" : "未触发"}
              </span>
            </li>
          ))}
        </ul>
      </section>

      <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-5">
        <h3 className="font-medium">自选与止损</h3>
        {data.in_watchlist ? (
          <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end">
            <label className="text-sm text-[#6f675c]">
              止损比例（%）
              <Input className="mt-1 w-32" type="number" min={0.5} max={40} step={0.5} value={stop} onChange={(event) => setStop(event.target.value)} />
            </label>
            <Button disabled={busy !== ""} onClick={() => void saveStop()}>
              {busy === "stop" ? "保存中…" : "保存止损"}
            </Button>
            <Button variant="outline" disabled={busy !== ""} onClick={() => void resetRef()}>
              {busy === "ref" ? "更新中…" : "参考价改为现价"}
            </Button>
            <Button variant="danger" disabled={busy !== ""} onClick={() => void toggleWatch()}>
              {busy === "watch" ? "处理中…" : "移出盯盘"}
            </Button>
          </div>
        ) : (
          <div className="mt-3">
            <p className="text-sm text-[#6f675c]">加入自选后可以设置这只股票的止损。参考价会取加入时的价格。</p>
            <Button className="mt-3" disabled={busy !== ""} onClick={() => void toggleWatch()}>
              {busy === "watch" ? "处理中…" : "加入盯盘"}
            </Button>
          </div>
        )}
        {note && <p className="mt-3 text-sm text-[#3c372f]">{note}</p>}
      </section>

      <ShockPad enabled={(data.quote_source ?? meta?.quote_source) === "mock"} code={data.code} onDone={() => setNote("")} />
      {error && <p className="text-sm text-[#9d3428]">{error}</p>}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-[#f7f1e6] px-3 py-2">
      <dt className="text-xs text-[#6f675c]">{label}</dt>
      <dd className="num mt-1">{value}</dd>
    </div>
  );
}
