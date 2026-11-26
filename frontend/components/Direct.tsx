"use client";

import { send } from "@/lib/send";
import { useState } from "react";

type Result = { after: string; what_changed: string; next: string };

// A small form beside something a stage made: the director says what is wrong and how to fix
// it, and the Reviser agent changes that one thing and remakes it.
export function Direct({
  slug,
  target,
  shot,
  label,
  placeholder,
  waiting,
  reroll,
}: {
  slug: string;
  target: "picture" | "line" | "motion" | "score" | "look" | "world";
  shot?: string;
  label: string;
  placeholder: string;
  waiting: string;
  reroll?: string;
}) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState("");
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);
  const [result, setResult] = useState<Result | null>(null);

  async function sendNote(again: boolean) {
    setBusy(true);
    setProblem(null);
    setResult(null);
    try {
      const response = await send(`/api/films/${slug}/direct`, { target, shot, note, reroll: again });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "The change could not be made.");
      setResult(body);
      setNote("");
    } catch (err) {
      setProblem(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  }

  if (!open) {
    return (
      <button type="button" className="direct-open" onClick={() => setOpen(true)}>
        {label}
      </button>
    );
  }
  return (
    <form
      className="direct"
      onSubmit={(event) => {
        event.preventDefault();
        sendNote(false);
      }}
    >
      <label>
        {label}
        <textarea
          value={note}
          onChange={(event) => setNote(event.target.value)}
          placeholder={placeholder}
          maxLength={600}
          disabled={busy}
          autoFocus
        />
      </label>
      <div className="direct-keys">
        <button type="submit" disabled={busy || note.trim().length < 5}>
          {busy ? waiting : "Make this change"}
        </button>
        {reroll && (
          <button type="button" className="quiet-button" disabled={busy} onClick={() => sendNote(true)}>
            {reroll}
          </button>
        )}
        <button type="button" className="quiet-button" disabled={busy} onClick={() => setOpen(false)}>
          Close
        </button>
      </div>
      {problem && (
        <p className="bad" role="alert">
          {problem}
        </p>
      )}
      {result && (
        <p className="direct-done" role="status">
          <b>Changed.</b> {result.what_changed} {result.next}
        </p>
      )}
    </form>
  );
}
