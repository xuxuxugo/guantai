export type Level = "observe" | "anomaly" | "risk";

export type WatchItem = {
  code: string;
  name: string;
  price: number;
  prev_close: number;
  change_pct: number;
  volume_ratio: number;
  status: Level;
  status_label: string;
  latest_signal: string;
  stop_loss_pct: number;
  ref_price: number;
  stale?: boolean;
};

export type WatchlistResponse = {
  items: WatchItem[];
  trading_hours_only: boolean;
  trading_session_open: boolean;
  disclaimer: string;
  quote_source?: string;
  quote_stale?: boolean;
  session_label?: string;
};

export type AlertEvent = {
  id: number;
  code: string;
  name: string;
  level: Level;
  level_label: string;
  rule_key: string;
  title: string;
  reason: string;
  price: number;
  change_pct: number;
  created_at: string;
};

export type RuleInput = {
  breakout_20d_enabled: boolean;
  swing_enabled: boolean;
  swing_window_minutes: number;
  swing_threshold_pct: number;
  stop_loss_enabled: boolean;
  default_stop_loss_pct: number;
  volume_spike_enabled: boolean;
  volume_ratio_threshold: number;
  trading_hours_only: boolean;
};

export type Rules = RuleInput & { trading_session_open: boolean };

export type Candle = { date: string; open: number; high: number; low: number; close: number };

export type Trigger = {
  rule_key: string;
  title: string;
  enabled: boolean;
  hit: boolean;
  level: Level | "none";
  detail: string;
};

export type StockDetail = {
  code: string;
  name: string;
  price: number;
  prev_close: number;
  open: number;
  high: number;
  low: number;
  change_pct: number;
  volume_ratio: number;
  high_20d: number;
  in_watchlist: boolean;
  stop_loss_pct: number | null;
  ref_price: number | null;
  status: Level;
  status_label: string;
  triggers: Trigger[];
  candles: Candle[];
  disclaimer: string;
  stale?: boolean;
  quote_source?: string;
  session_label?: string;
};

export type IndexQuote = {
  symbol: string;
  code: string;
  name: string;
  price: number;
  prev_close: number;
  change_pct: number;
  turnover: number;
  stale: boolean;
};

export type MarketBreadth = {
  up: number;
  down: number;
  flat: number;
  total: number;
  source: string;
  stale: boolean;
  note: string;
};

export type MarketOverview = {
  indices: IndexQuote[];
  breadth?: MarketBreadth | null;
  quote_source: string;
  quote_stale: boolean;
  session_label: string;
  disclaimer: string;
};

export type Meta = {
  name: string;
  disclaimer: string;
  demo_user: string;
  scan_interval_seconds: number;
  demo_auto_pulse: boolean;
  trading_session_open: boolean;
  market: string;
  quote_source?: string;
  offhours_scan_interval_seconds?: number;
  session_label?: string;
};

export type ShockResult = {
  code: string;
  name: string;
  price: number;
  change_pct: number;
  alerts: AlertEvent[];
  note: string;
  disclaimer: string;
};

export type ShockKind = "swing_up" | "swing_down" | "breakout" | "volume" | "stop";

export type PoolRow = {
  code: string;
  name: string;
  sector: string;
  price: number;
  prev_close: number;
  change_pct: number;
  volume_ratio: number;
  turnover: number;
  market_cap: number;
  stale: boolean;
};

export type SectorRow = { sector: string; change_pct: number; count: number };

export type PoolSnapshot = {
  rows: PoolRow[];
  sectors: SectorRow[];
  rankings: Rankings;
  stale: boolean;
  pool_size: number;
  note: string;
  disclaimer: string;
};

export type Rankings = { gainers: PoolRow[]; losers: PoolRow[]; turnover: PoolRow[] };

export type RankingsResult = {
  rankings: Rankings;
  sectors: SectorRow[];
  stale: boolean;
  note: string;
  disclaimer: string;
};

export type ScreenResult = {
  rows: PoolRow[];
  stale: boolean;
  pool_size: number;
  note: string;
  disclaimer: string;
};

export type TechnicalPoint = {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
  dif: number | null;
  dea: number | null;
  hist: number | null;
  rsi: number | null;
  k: number | null;
  d: number | null;
  j: number | null;
  mid: number | null;
  upper: number | null;
  lower: number | null;
};

export type TechnicalView = {
  code: string;
  name: string;
  period: string;
  series: TechnicalPoint[];
  latest: TechnicalPoint | null;
  rating: { label: string; score: number; reasons: string[] };
  minute: { time: string; price: number }[];
  minute_note: string;
  stale: boolean;
  note: string;
  disclaimer: string;
};

export type FinancialRow = {
  period: string;
  revenue: number | null;
  profit: number | null;
  revenue_yoy: number | null;
  profit_yoy: number | null;
  roe: number | null;
  gross_margin: number | null;
  debt_ratio: number | null;
  eps: number | null;
  bps: number | null;
};

export type FinancialView = {
  code: string;
  name: string;
  rows: FinancialRow[];
  stale: boolean;
  source: string;
  note: string;
  disclaimer: string;
};

export type BacktestResult = {
  code: string;
  name: string;
  strategy: string;
  title: string;
  total_return_pct: number;
  max_drawdown_pct: number;
  win_rate_pct: number;
  trade_count: number;
  equity: { date: string; equity: number }[];
  trades: { date: string; side: string; price: number; pnl_pct: number | null }[];
  note: string;
  disclaimer: string;
};

export type AgentReport = {
  code: string;
  name: string;
  demo: boolean;
  source: string;
  note: string;
  roles: { role: string; text: string }[];
  disclaimer: string;
};

export type DigestView = {
  session_label: string;
  indices: IndexQuote[];
  leaders: Rankings;
  watch: { code: string; name: string; price: number; change_pct: number; status_label: string; latest_signal: string }[];
  stale: boolean;
  note: string;
  disclaimer: string;
};

export type NewsFeed = {
  column: string;
  label: string;
  columns: { id: string; label: string }[];
  items: { title: string; url: string; summary: string; source: string; published_at: string }[];
  stale: boolean;
  source: string;
  note: string;
  disclaimer: string;
};

export type CalendarView = {
  source: string;
  stale: boolean;
  note: string;
  events: { date: string; region: string; title: string; importance: string }[];
  disclaimer: string;
};

export type OpportunityView = {
  vix: { symbol: string; name: string; price: number; change_pct: number; stale: boolean; source?: string; note?: string };
  signals: { code: string; name: string; status_label: string; latest_signal: string; change_pct: number }[];
  unavailable: { name: string; note: string }[];
  disclaimer: string;
};

export type DataCenterView = {
  quote_source: string;
  market_name: string;
  session_label: string;
  indices: IndexQuote[];
  index_stale: boolean;
  pool: PoolRow[];
  pool_stale: boolean;
  watchlist: { code: string; name: string; price: number; change_pct: number; volume_ratio: number; stale: boolean }[];
  note: string;
  disclaimer: string;
};
