import type { Metadata } from "next";
import type { ReactNode } from "react";
import "./globals.css";
import { Shell } from "@/components/shell";

export const metadata: Metadata = {
  title: "观澜盯盘",
  description: "自选股观察、异动和风控提醒。仅供研究参考，不构成投资建议。",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="zh-CN">
      <body className="antialiased">
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
