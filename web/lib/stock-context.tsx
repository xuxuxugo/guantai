"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

const STORAGE_KEY = "guanlan.stock";
const DEFAULT_CODE = "600519";

export type StockRef = {
  code: string;
  name?: string;
};

type StockContextValue = {
  code: string;
  name?: string;
  setStock: (code: string, name?: string) => void;
  ready: boolean;
};

const StockContext = createContext<StockContextValue>({
  code: DEFAULT_CODE,
  setStock: () => undefined,
  ready: false,
});

function normalizeCode(raw: string) {
  const digits = raw.replace(/\D/g, "").slice(0, 6);
  return /^\d{6}$/.test(digits) ? digits : DEFAULT_CODE;
}

function readStored(): StockRef {
  if (typeof window === "undefined") return { code: DEFAULT_CODE };
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return { code: DEFAULT_CODE };
    const parsed = JSON.parse(raw) as StockRef;
    return { code: normalizeCode(parsed.code || DEFAULT_CODE), name: parsed.name };
  } catch {
    return { code: DEFAULT_CODE };
  }
}

export function StockProvider({ children }: { children: ReactNode }) {
  const [stock, setStockState] = useState<StockRef>({ code: DEFAULT_CODE });
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setStockState(readStored());
    setReady(true);
  }, []);

  const setStock = useCallback((code: string, name?: string) => {
    const next: StockRef = { code: normalizeCode(code), name: name?.trim() || undefined };
    setStockState(next);
    try {
      sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      /* ignore quota */
    }
  }, []);

  const value = useMemo(
    () => ({ code: stock.code, name: stock.name, setStock, ready }),
    [stock.code, stock.name, setStock, ready],
  );

  return <StockContext.Provider value={value}>{children}</StockContext.Provider>;
}

export function useStock() {
  return useContext(StockContext);
}

export function researchHref(path: string, code: string) {
  if (path.startsWith("/stocks")) return `/stocks/${normalizeCode(code)}`;
  return `${path}?code=${normalizeCode(code)}`;
}

export { DEFAULT_CODE, normalizeCode };
