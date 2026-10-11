"use client";

import { useEffect, useState } from "react";
import { api, errorMessage } from "@/lib/api";
import type { ShockKind } from "@/lib/types";
import { Button } from "@/components/ui/button";

const KINDS: { kind: ShockKind; label: string }[] = [
  { kind: "swing_up", label: "拉升 +3.6%" },
  { kind: "swing_down", label: "回撤 -3.6%" },
  { kind: "breakout", label: "突破高点" },
  { kind: "volume", label: "放量" },
  { kind: "stop", label: "触及止损" },
];

export function ShockPad({
  code,
  options,
  onDone,
  enabled = true,
}: {
  code?: string;
  options?: { code: string; name: string }[];
  onDone?: () => void;
  enabled?: boolean;
}) {
  const [selected, setSelected] = useState(code || options?.[0]?.code || "");
  const [pending, setPending] = useState<ShockKind | null>(null);
  const [note, setNote] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    if (code) setSelected(code);
  }, [code]);

  useEffect(() => {
    if (!code && options && options.length > 0 && !options.some((item) => item.code === selected)) {
      setSelected(options[0].code);
    }
  }, [code, options, selected]);

  async function fire(kind: ShockKind) {
    if (!selected) return;
    setPending(kind);
    setError("");
    setNote("");
    try {
      const result = await api.shock(selected, kind);
      setNote(result.note);
      onDone?.();
    } catch (err) {
      setError(errorMessage(err, "模拟冲击没有发出去"));
    } finally {
      setPending(null);
    }
  }

  if (!enabled) {
    return (
      <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
        <h2 className="font-medium">模拟冲击已关闭</h2>
        <p className="mt-1 text-sm leading-6 text-[#6f675c]">
          当前使用腾讯行情，价格来自公开接口。要在没有行情时改写价格看告警，把 QUOTE_SOURCE 设为 mock，需要自动脉冲再打开 DEMO_AUTO_PULSE。
        </p>
      </section>
    );
  }

  return (
    <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="font-medium">模拟冲击</h2>
          <p className="mt-1 text-sm leading-6 text-[#6f675c]">只改写演示价格，用来看告警怎么出现。不会连接券商，也不会下单。</p>
        </div>
        {options && (
          <label className="text-sm text-[#6f675c]">
            股票
            <select
              className="ml-2 h-9 rounded-md border border-[#d9d0c1] bg-white px-2 text-[#1c1915]"
              value={selected}
              onChange={(event) => setSelected(event.target.value)}
            >
              {options.length === 0 && <option value="">自选是空的</option>}
              {options.map((item) => (
                <option key={item.code} value={item.code}>
                  {item.name} {item.code}
                </option>
              ))}
            </select>
          </label>
        )}
      </div>
      <div className="mt-3 flex flex-wrap gap-2">
        {KINDS.map((item) => (
          <Button
            key={item.kind}
            size="sm"
            variant={item.kind === "stop" || item.kind === "swing_down" ? "danger" : "outline"}
            disabled={!selected || pending !== null}
            onClick={() => fire(item.kind)}
          >
            {pending === item.kind ? "发送中…" : item.label}
          </Button>
        ))}
      </div>
      {note && <p className="mt-3 text-sm text-[#17653d]">{note}</p>}
      {error && <p className="mt-3 text-sm text-[#9d3428]">{error}</p>}
    </section>
  );
}
