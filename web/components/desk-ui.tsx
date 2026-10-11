"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Input } from "@/components/ui/input";

export function LoadingBlock({ label = "正在取数" }: { label?: string }) {
  return (
    <div className="space-y-2" aria-busy="true">
      <p className="text-sm text-[#6f675c]">{label}</p>
      {Array.from({ length: 3 }).map((_, index) => (
        <div key={index} className="h-16 animate-pulse rounded-lg bg-[#e7e1d6]" />
      ))}
    </div>
  );
}

export function ErrorNote({ text }: { text: string }) {
  if (!text) return null;
  return <p className="rounded-md bg-[#f7e7e2] px-3 py-2 text-sm text-[#8d3428]">{text}</p>;
}

export function Note({ text }: { text?: string }) {
  if (!text) return null;
  return <p className="text-sm leading-6 text-[#6f675c]">{text}</p>;
}

export function CodePicker({
  code,
  onChange,
  compact = false,
}: {
  code: string;
  onChange: (code: string, name?: string) => void;
  compact?: boolean;
}) {
  const [query, setQuery] = useState("");
  const [hits, setHits] = useState<{ code: string; name: string }[]>([]);

  useEffect(() => {
    const keyword = query.trim();
    if (!keyword) {
      setHits([]);
      return;
    }
    const timer = window.setTimeout(() => {
      api.search(keyword).then((result) => setHits(result.items)).catch(() => setHits([]));
    }, 200);
    return () => window.clearTimeout(timer);
  }, [query]);

  return (
    <div className={`rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] ${compact ? "p-3" : "p-4"}`}>
      <div className="flex flex-wrap items-end justify-between gap-2">
        <label className="block min-w-[12rem] flex-1 text-sm text-[#6f675c]">
          换一只股票
          <Input
            className="mt-1"
            value={query}
            placeholder="600519 或 茅台 · 也可用顶栏选股"
            onChange={(event) => setQuery(event.target.value)}
          />
        </label>
        <p className="num pb-2 text-sm text-[#1c1915]">当前 {code}</p>
      </div>
      {hits.length > 0 && (
        <ul className="mt-2 divide-y divide-[#eee6d8] rounded-md border border-[#eee6d8] bg-white">
          {hits.map((hit) => (
            <li key={hit.code}>
              <button
                type="button"
                className="flex w-full items-center justify-between px-3 py-2 text-left text-sm hover:bg-[#f7f1e6]"
                onClick={() => {
                  onChange(hit.code, hit.name);
                  setQuery("");
                  setHits([]);
                }}
              >
                <span>{hit.name}</span>
                <span className="num text-[#6f675c]">{hit.code}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
      {!compact && (
        <p className="mt-2 text-xs text-[#6f675c]">顶栏选股会带到所有研究页。选股池按成交额取样，不是全市场。</p>
      )}
    </div>
  );
}

export function Spark({ values, color = "#c24532" }: { values: number[]; color?: string }) {
  if (values.length < 2) return <p className="text-sm text-[#6f675c]">暂无曲线</p>;
  const width = 640;
  const height = 160;
  const pad = 10;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const d = values
    .map((value, index) => {
      const x = pad + (index / (values.length - 1)) * (width - pad * 2);
      const y = pad + ((max - value) / span) * (height - pad * 2);
      return `${index === 0 ? "M" : "L"}${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg viewBox={`0 0 ${width} ${height}`} className="h-40 w-full" role="img">
      <path d={d} fill="none" stroke={color} strokeWidth="2" />
    </svg>
  );
}
