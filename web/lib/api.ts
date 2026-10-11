import type {
  AgentReport,
  AlertEvent,
  BacktestResult,
  CalendarView,
  DataCenterView,
  DigestView,
  FinancialView,
  MarketOverview,
  Meta,
  NewsFeed,
  OpportunityView,
  PoolSnapshot,
  RankingsResult,
  RuleInput,
  Rules,
  ScreenResult,
  ShockKind,
  ShockResult,
  StockDetail,
  TechnicalView,
  WatchlistResponse,
} from "@/lib/types";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/backend${path}`, {
      ...init,
      cache: "no-store",
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
    });
  } catch {
    throw new ApiError("行情服务暂时没有回应", 0);
  }

  const text = await response.text();
  let payload: { detail?: unknown } | null = null;
  if (text) {
    try {
      payload = JSON.parse(text) as { detail?: unknown };
    } catch {
      payload = { detail: text };
    }
  }
  if (!response.ok) {
    const detail = payload?.detail;
    throw new ApiError(typeof detail === "string" ? detail : "请求没有完成", response.status);
  }
  return payload as T;
}

export function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback;
}

export const api = {
  meta: () => request<Meta>("/api/meta"),
  market: () => request<MarketOverview>("/api/market"),
  pool: () => request<PoolSnapshot>("/api/pool"),
  screen: (query: string) => request<ScreenResult>(`/api/screen${query}`),
  rankings: () => request<RankingsResult>("/api/rankings"),
  technical: (code: string, period: string, minute = false) =>
    request<TechnicalView>(`/api/stocks/${code}/technical?period=${period}&minute=${minute ? 1 : 0}`),
  financials: (code: string) => request<FinancialView>(`/api/stocks/${code}/financials`),
  backtest: (code: string, strategy: string) => request<BacktestResult>(`/api/backtest?code=${code}&strategy=${strategy}`),
  agent: (code: string, question: string) =>
    request<AgentReport>(`/api/agent?code=${code}&question=${encodeURIComponent(question)}`),
  digest: () => request<DigestView>("/api/digest"),
  news: (column: string) => request<NewsFeed>(`/api/news?column=${column}`),
  calendar: () => request<CalendarView>("/api/calendar"),
  opportunities: () => request<OpportunityView>("/api/opportunities"),
  datacenter: () => request<DataCenterView>("/api/datacenter"),
  watchlist: () => request<WatchlistResponse>("/api/watchlist"),
  addWatch: (code: string) => request<{ code: string; name: string }>("/api/watchlist", { method: "POST", body: JSON.stringify({ code }) }),
  removeWatch: (code: string) => request<{ ok: boolean }>(`/api/watchlist/${code}`, { method: "DELETE" }),
  patchWatch: (code: string, body: { stop_loss_pct?: number; reset_ref?: boolean }) =>
    request<{ code: string; stop_loss_pct: number; ref_price: number }>(`/api/watchlist/${code}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  alerts: () => request<{ events: AlertEvent[]; disclaimer: string }>("/api/alerts?limit=100"),
  rules: () => request<Rules>("/api/rules"),
  saveRules: (body: RuleInput) => request<Rules>("/api/rules", { method: "PUT", body: JSON.stringify(body) }),
  stock: (code: string) => request<StockDetail>(`/api/stocks/${encodeURIComponent(code)}`),
  search: (q: string) => request<{ items: { code: string; name: string }[] }>(`/api/stocks/search?q=${encodeURIComponent(q)}`),
  shock: (code: string, kind: ShockKind) =>
    request<ShockResult>("/api/demo/shock", { method: "POST", body: JSON.stringify({ code, kind }) }),
};
