"use client";

import { useEffect, useState, type ReactNode } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SwitchToggle } from "@/components/ui/switch";
import { api, errorMessage } from "@/lib/api";
import type { RuleInput, Rules } from "@/lib/types";

const EMPTY: RuleInput = {
  breakout_20d_enabled: true,
  swing_enabled: true,
  swing_window_minutes: 5,
  swing_threshold_pct: 3,
  stop_loss_enabled: true,
  default_stop_loss_pct: 8,
  volume_spike_enabled: true,
  volume_ratio_threshold: 2.5,
  trading_hours_only: false,
};

export function RuleCenter() {
  const [form, setForm] = useState<RuleInput>(EMPTY);
  const [sessionOpen, setSessionOpen] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  useEffect(() => {
    let stop = false;
    api.rules().then((data) => {
      if (stop) return;
      setForm(toInput(data));
      setSessionOpen(data.trading_session_open);
      setLoading(false);
    }).catch((err) => {
      if (stop) return;
      setError(errorMessage(err, "规则暂时没有取到"));
      setLoading(false);
    });
    return () => {
      stop = true;
    };
  }, []);

  function update<K extends keyof RuleInput>(key: K, value: RuleInput[K]) {
    setForm((current) => ({ ...current, [key]: value }));
    setMessage("");
  }

  async function save() {
    const numbers = [form.swing_window_minutes, form.swing_threshold_pct, form.default_stop_loss_pct, form.volume_ratio_threshold];
    if (!numbers.every((value) => Number.isFinite(value))) {
      setMessage("请把窗口、阈值和止损填成数字");
      return;
    }
    setSaving(true);
    setMessage("");
    try {
      const saved = await api.saveRules(form);
      setForm(toInput(saved));
      setSessionOpen(saved.trading_session_open);
      setMessage("已保存。下一次扫描按新规则算。模拟行情下，手动冲击会立刻生效。");
    } catch (err) {
      setMessage(errorMessage(err, "没有保存成功"));
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <div className="space-y-3" aria-busy="true">
        {Array.from({ length: 3 }).map((_, index) => (
          <div key={index} className="h-28 animate-pulse rounded-xl bg-[#e7e1d6]" />
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {error && <p className="rounded-md bg-[#f7e7e2] px-3 py-2 text-sm text-[#8d3428]">{error}</p>}
      <div className="grid gap-4 lg:grid-cols-2">
        <RuleCard
          title="突破 20 日高点"
          description="现价不低于近 20 个交易日最高价时，记一条异动。"
          checked={form.breakout_20d_enabled}
          onCheckedChange={(value) => update("breakout_20d_enabled", value)}
          label="开启突破 20 日高点"
        />
        <RuleCard
          title="短窗口涨跌"
          description="默认看 5 分钟内涨跌是否超过 3%。窗口和阈值都可以改。"
          checked={form.swing_enabled}
          onCheckedChange={(value) => update("swing_enabled", value)}
          label="开启短窗口涨跌"
        >
          <div className="mt-4 flex flex-wrap gap-3">
            <NumberField
              label="窗口（分钟）"
              value={form.swing_window_minutes}
              min={1}
              max={30}
              step={1}
              disabled={!form.swing_enabled}
              onChange={(value) => update("swing_window_minutes", value)}
            />
            <NumberField
              label="阈值（%）"
              value={form.swing_threshold_pct}
              min={0.5}
              max={20}
              step={0.1}
              disabled={!form.swing_enabled}
              onChange={(value) => update("swing_threshold_pct", value)}
            />
          </div>
        </RuleCard>
        <RuleCard
          title="止损提醒"
          description="新加入自选时使用这个比例。已经在盯盘台里的股票，沿用各自详情页上的止损。"
          checked={form.stop_loss_enabled}
          onCheckedChange={(value) => update("stop_loss_enabled", value)}
          label="开启止损提醒"
        >
          <div className="mt-4">
            <NumberField
              label="默认止损（%）"
              value={form.default_stop_loss_pct}
              min={0.5}
              max={40}
              step={0.5}
              disabled={!form.stop_loss_enabled}
              onChange={(value) => update("default_stop_loss_pct", value)}
            />
          </div>
        </RuleCard>
        <RuleCard
          title="量比突增"
          description="量比高于阈值时记异动。腾讯行情用接口里的量比；模拟行情是演示用的相对活跃度。"
          checked={form.volume_spike_enabled}
          onCheckedChange={(value) => update("volume_spike_enabled", value)}
          label="开启量比突增"
        >
          <div className="mt-4">
            <NumberField
              label="量比阈值"
              value={form.volume_ratio_threshold}
              min={1.1}
              max={10}
              step={0.1}
              disabled={!form.volume_spike_enabled}
              onChange={(value) => update("volume_ratio_threshold", value)}
            />
          </div>
        </RuleCard>
      </div>
      <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-5">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="font-medium">仅交易时段出警</h2>
            <p className="mt-1 text-sm leading-6 text-[#6f675c]">
              沪深时段按北京时间 9:30–11:30、13:00–15:00，周末不写告警。当前{sessionOpen ? "在交易时段" : "不在交易时段"}。
              关掉之后，全天都会按规则写告警。模拟冲击只在 QUOTE_SOURCE=mock 时可用，并且不受这个开关限制。
            </p>
          </div>
          <SwitchToggle
            checked={form.trading_hours_only}
            onCheckedChange={(value) => update("trading_hours_only", value)}
            aria-label="仅交易时段出警"
          />
        </div>
      </section>
      <div className="sticky bottom-4 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[#1c1915] px-4 py-3 text-[#f6f1e7]">
        <p className="text-sm">{message || "改完记得保存。仅供研究参考，不构成投资建议。"}</p>
        <Button variant="light" disabled={saving || Boolean(error)} onClick={() => void save()}>
          {saving ? "保存中…" : "保存规则"}
        </Button>
      </div>
    </div>
  );
}

function toInput(data: Rules): RuleInput {
  return {
    breakout_20d_enabled: data.breakout_20d_enabled,
    swing_enabled: data.swing_enabled,
    swing_window_minutes: data.swing_window_minutes,
    swing_threshold_pct: data.swing_threshold_pct,
    stop_loss_enabled: data.stop_loss_enabled,
    default_stop_loss_pct: data.default_stop_loss_pct,
    volume_spike_enabled: data.volume_spike_enabled,
    volume_ratio_threshold: data.volume_ratio_threshold,
    trading_hours_only: data.trading_hours_only,
  };
}

function RuleCard({
  title,
  description,
  checked,
  onCheckedChange,
  label,
  children,
}: {
  title: string;
  description: string;
  checked: boolean;
  onCheckedChange: (value: boolean) => void;
  label: string;
  children?: ReactNode;
}) {
  return (
    <section className="rounded-xl border border-[#e0d8c8] bg-[#fbf8f2] p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="font-medium">{title}</h2>
          <p className="mt-1 text-sm leading-6 text-[#6f675c]">{description}</p>
        </div>
        <SwitchToggle checked={checked} onCheckedChange={onCheckedChange} aria-label={label} />
      </div>
      {children}
    </section>
  );
}

function NumberField({
  label,
  value,
  min,
  max,
  step,
  disabled,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  disabled: boolean;
  onChange: (value: number) => void;
}) {
  return (
    <label className="block text-sm text-[#6f675c]">
      {label}
      <Input
        className="mt-1 w-32"
        type="number"
        inputMode="decimal"
        min={min}
        max={max}
        step={step}
        disabled={disabled}
        value={Number.isFinite(value) ? value : ""}
        onChange={(event) => onChange(Number(event.target.value))}
      />
    </label>
  );
}
