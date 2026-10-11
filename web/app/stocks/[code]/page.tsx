"use client";

import { useParams } from "next/navigation";
import { StockDetail } from "@/components/stock-detail";

export default function Page() {
  const params = useParams<{ code: string }>();
  const code = Array.isArray(params.code) ? params.code[0] : params.code;
  return <StockDetail code={code ?? ""} />;
}
