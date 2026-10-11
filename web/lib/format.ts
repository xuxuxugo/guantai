export function formatPrice(value: number) {
  return value.toFixed(2);
}

export function formatPct(value: number) {
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(2)}%`;
}

export function formatYiYuan(yuan: number | null) {
  if (yuan == null) return "—";
  const yi = yuan / 100000000;
  const abs = Math.abs(yi);
  if (abs >= 10000) return `${(yi / 10000).toFixed(2)}万亿`;
  return `${yi.toFixed(2)}亿`;
}

export function formatCapYi(yi: number) {
  if (!yi) return "—";
  if (yi >= 10000) return `${(yi / 10000).toFixed(2)}万亿`;
  return `${yi.toFixed(0)}亿`;
}

export function formatTurnover(yuan: number) {
  if (!yuan) return "—";
  const yi = yuan / 100000000;
  if (yi >= 10000) return `${yi.toFixed(0)}亿`;
  if (yi >= 100) return `${yi.toFixed(1)}亿`;
  return `${yi.toFixed(2)}亿`;
}

export function priceTone(value: number) {
  if (value > 0) return "text-[#c24532]";
  if (value < 0) return "text-[#1d7a4a]";
  return "text-[#6f675c]";
}

export function formatTime(iso: string) {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

export function formatClock(date: Date) {
  return new Intl.DateTimeFormat("zh-CN", {
    timeZone: "Asia/Shanghai",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}
