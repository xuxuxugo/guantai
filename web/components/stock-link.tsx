"use client";

import Link from "next/link";
import type { CSSProperties, ReactNode } from "react";
import { researchHref, useStock } from "@/lib/stock-context";

type Props = {
  code: string;
  name?: string;
  /** Default: research 个股信息 */
  to?: "info" | "technical" | "detail" | "watch";
  href?: string;
  className?: string;
  style?: CSSProperties;
  children: ReactNode;
};

export function StockLink({ code, name, to = "info", href, className, style, children }: Props) {
  const { setStock } = useStock();
  const target =
    href ||
    (to === "detail"
      ? `/stocks/${code}`
      : to === "watch"
        ? "/watch"
        : to === "technical"
          ? researchHref("/technical", code)
          : researchHref("/info", code));

  return (
    <Link
      href={target}
      className={className}
      style={style}
      onClick={() => setStock(code, name)}
    >
      {children}
    </Link>
  );
}
