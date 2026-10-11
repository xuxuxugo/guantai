"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect, useRef } from "react";
import { normalizeCode, researchHref, useStock } from "@/lib/stock-context";

/** Sync page code with global stock context + URL ?code= */
export function useResearchCode(initialCode: string) {
  const { code, setStock, ready } = useStock();
  const router = useRouter();
  const path = usePathname();
  const seeded = useRef(false);

  useEffect(() => {
    if (!ready || seeded.current) return;
    seeded.current = true;
    const fromUrl = normalizeCode(initialCode);
    if (fromUrl !== code) {
      setStock(fromUrl);
    }
  }, [ready, initialCode, code, setStock]);

  function setCode(next: string, name?: string) {
    const normalized = normalizeCode(next);
    setStock(normalized, name);
    const base = path.split("?")[0];
    router.replace(researchHref(base, normalized), { scroll: false });
  }

  return { code: ready ? code : normalizeCode(initialCode), setCode };
}
