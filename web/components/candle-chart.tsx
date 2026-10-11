import type { Candle } from "@/lib/types";

export function CandleChart({ candles, label = "近40个交易日K线" }: { candles: Candle[]; label?: string }) {
  if (candles.length === 0) {
    return <p className="text-sm text-[#6f675c]">暂无走势。</p>;
  }
  const width = 720;
  const height = 260;
  const pad = { l: 56, r: 12, t: 16, b: 28 };
  const max = Math.max(...candles.map((item) => item.high));
  const min = Math.min(...candles.map((item) => item.low));
  const span = max - min || 1;
  const innerW = width - pad.l - pad.r;
  const innerH = height - pad.t - pad.b;
  const slot = innerW / candles.length;
  const y = (value: number) => pad.t + ((max - value) / span) * innerH;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label={label} className="h-auto w-full">
      {[0, 0.5, 1].map((mark) => {
        const value = max - span * mark;
        const yPos = y(value);
        return (
          <g key={mark}>
            <line x1={pad.l} x2={width - pad.r} y1={yPos} y2={yPos} stroke="#e0d8c8" strokeDasharray="3 4" />
            <text x={pad.l - 8} y={yPos + 4} textAnchor="end" fontSize="11" fill="#6f675c">
              {value.toFixed(2)}
            </text>
          </g>
        );
      })}
      {candles.map((candle, index) => {
        const x = pad.l + index * slot + slot / 2;
        const up = candle.close > candle.open;
        const flat = candle.close === candle.open;
        const color = flat ? "#8a8175" : up ? "#c24532" : "#1d7a4a";
        const bodyTop = y(Math.max(candle.open, candle.close));
        const bodyHeight = Math.max(1.5, Math.abs(y(candle.open) - y(candle.close)));
        return (
          <g key={candle.date}>
            <line x1={x} x2={x} y1={y(candle.high)} y2={y(candle.low)} stroke={color} strokeWidth="1.2" />
            <rect x={x - slot * 0.28} y={bodyTop} width={Math.max(2, slot * 0.56)} height={bodyHeight} fill={color} rx="0.6" />
          </g>
        );
      })}
      <text x={pad.l} y={height - 8} fontSize="11" fill="#6f675c">
        {candles[0]?.date.slice(5)}
      </text>
      <text x={width - pad.r} y={height - 8} textAnchor="end" fontSize="11" fill="#6f675c">
        {candles[candles.length - 1]?.date.slice(5)}
      </text>
    </svg>
  );
}
