import { formatPct, formatPrice, formatTurnover } from "@/lib/format";
import type { MarketOverview } from "@/lib/types";

function indexTone(value: number) {
  if (value > 0) return "text-[#ffb4a8]";
  if (value < 0) return "text-[#8fd4ae]";
  return "text-[#cfc6b6]";
}

export function MarketStrip({
  data,
  loading,
  error,
}: {
  data: MarketOverview | null;
  loading: boolean;
  error: string;
}) {
  const breadth = data?.breadth;
  return (
    <section className="rounded-xl border border-[#e0d8c8] bg-[#1c1915] p-4 text-[#f3efe6]" aria-label="大盘观察">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-serif text-lg">大盘观察</h2>
        <p className="text-xs text-[#cfc6b6]">
          {data?.session_label || "指数"}
          {data?.quote_stale ? " · 行情延迟，显示上次指数" : ""}
        </p>
      </div>
      {loading && !data && (
        <div className="mt-3 grid gap-3 sm:grid-cols-3" aria-busy="true">
          {Array.from({ length: 3 }).map((_, index) => (
            <div key={index} className="h-20 animate-pulse rounded-lg bg-white/10" />
          ))}
        </div>
      )}
      {error && !data && <p className="mt-3 text-sm text-[#f0b2a8]">{error}</p>}
      {data && (
        <ul className="mt-3 grid gap-3 sm:grid-cols-3">
          {data.indices.map((item) => (
            <li key={item.symbol} className="rounded-lg bg-white/5 px-3 py-3">
              <div className="flex items-baseline justify-between gap-2">
                <p className="font-medium">{item.name}</p>
                <span className="num text-xs text-[#cfc6b6]">{item.symbol}</span>
              </div>
              <p className={`num mt-2 text-2xl ${item.price > 0 ? indexTone(item.change_pct) : "text-[#cfc6b6]"}`}>
                {item.price > 0 ? formatPrice(item.price) : "—"}
              </p>
              <p className={`num text-sm ${indexTone(item.change_pct)}`}>{item.price > 0 ? formatPct(item.change_pct) : "—"}</p>
              <p className="mt-2 text-xs text-[#cfc6b6]">
                成交额 <span className="num text-[#f3efe6]">{formatTurnover(item.turnover)}</span>
              </p>
            </li>
          ))}
        </ul>
      )}
      {breadth && (
        <div className="mt-3 rounded-lg bg-white/5 px-3 py-3">
          <div className="flex flex-wrap items-baseline justify-between gap-2">
            <p className="text-sm font-medium">涨跌家数</p>
            <p className="text-xs text-[#cfc6b6]">
              {breadth.source || "公开源"}
              {breadth.stale ? " · 延迟" : ""}
            </p>
          </div>
          {breadth.total > 0 ? (
            <>
              <p className="num mt-2 text-sm">
                <span className="text-[#ffb4a8]">上涨 {breadth.up}</span>
                <span className="mx-2 text-[#cfc6b6]">/</span>
                <span className="text-[#8fd4ae]">下跌 {breadth.down}</span>
                <span className="mx-2 text-[#cfc6b6]">/</span>
                <span className="text-[#cfc6b6]">平盘 {breadth.flat}</span>
              </p>
              <div className="mt-2 flex h-2 overflow-hidden rounded-full bg-white/10" aria-hidden="true">
                <span className="bg-[#c24532]" style={{ width: `${(breadth.up / breadth.total) * 100}%` }} />
                <span className="bg-[#6f675c]" style={{ width: `${(breadth.flat / breadth.total) * 100}%` }} />
                <span className="bg-[#1d7a4a]" style={{ width: `${(breadth.down / breadth.total) * 100}%` }} />
              </div>
            </>
          ) : (
            <p className="mt-2 text-sm text-[#cfc6b6]">{breadth.note || "涨跌家数暂时不可用。"}</p>
          )}
          {breadth.note && breadth.total > 0 && <p className="mt-2 text-xs text-[#cfc6b6]">{breadth.note}</p>}
        </div>
      )}
      <p className="mt-3 text-xs leading-5 text-[#cfc6b6]">指数只作观察。仅供研究参考，不构成投资建议。</p>
    </section>
  );
}
