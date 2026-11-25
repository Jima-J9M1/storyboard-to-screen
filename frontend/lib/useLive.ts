"use client";

import { useEffect, useState } from "react";

const REFRESH_MS = 5000;

// Keep a value in step with the repo: start from what the server rendered, then ask again
// every few seconds. The value only changes when the answer does, so open rows stay open.
export function useLive<T>(url: string, initial: T): { value: T; problem: string | null } {
  const [value, setValue] = useState(initial);
  const [problem, setProblem] = useState<string | null>(null);

  useEffect(() => {
    let last = JSON.stringify(initial);
    let stopped = false;

    async function refresh() {
      try {
        const response = await fetch(url, { cache: "no-store" });
        const body = await response.json();
        if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`);
        if (stopped) return;
        setProblem(null);
        const text = JSON.stringify(body);
        if (text !== last) {
          last = text;
          setValue(body);
        }
      } catch (err) {
        if (!stopped) setProblem(err instanceof Error ? err.message : String(err));
      }
    }

    const timer = setInterval(refresh, REFRESH_MS);
    return () => {
      stopped = true;
      clearInterval(timer);
    };
    // The page is rendered once per URL, so `initial` is only the starting point.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [url]);

  return { value, problem };
}
