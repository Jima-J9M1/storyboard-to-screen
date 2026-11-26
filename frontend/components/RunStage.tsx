"use client";

import { useState } from "react";

// A button that starts one stage, and shows what the stage said when it finished.
export function RunStage({ slug, stage, label, busy }: { slug: string; stage: string; label: string; busy: string | null }) {
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<{ ok: boolean; lines: string[] } | null>(null);
  const [problem, setProblem] = useState<string | null>(null);

  async function start() {
    setRunning(true);
    setResult(null);
    setProblem(null);
    try {
      const response = await fetch(`/api/films/${slug}/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ stage }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "The stage could not be started.");
      setResult(body);
    } catch (err) {
      setProblem(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  }

  const blocked = running || busy !== null;
  return (
    <div className="run-stage">
      <button type="button" onClick={start} disabled={blocked}>
        {running ? "Running. This can take a few minutes" : busy ? `Waiting: ${busy} is running` : label}
      </button>
      {problem && (
        <p className="bad" role="alert">
          {problem}
        </p>
      )}
      {result && (
        <div className={result.ok ? "run-result" : "run-result failed"} role="status">
          <b>{result.ok ? "Finished." : "It stopped before finishing."}</b>
          <ul>
            {result.lines.map((line, n) => (
              <li key={n}>{line}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
