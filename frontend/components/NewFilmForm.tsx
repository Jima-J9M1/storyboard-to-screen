"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function NewFilmForm() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [problem, setProblem] = useState<string | null>(null);

  async function startFilm(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const field = (name: string) => String(form.get(name) || "").trim();
    setBusy(true);
    setProblem(null);
    try {
      const response = await fetch("/api/films", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: field("title"),
          audience: field("audience"),
          feeling: field("feeling"),
          languages: field("languages").toLowerCase().split(/[\s,]+/).filter(Boolean),
        }),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || "The film could not be started.");
      router.push(`/films/${body.slug}`);
    } catch (err) {
      setProblem(err instanceof Error ? err.message : String(err));
      setBusy(false);
    }
  }

  return (
    <form className="new-film" onSubmit={startFilm}>
      <h2>Start a new film</h2>
      <label>
        Title
        <small>A person, place or story. It must match the name of a Wikipedia article.</small>
        <input name="title" required minLength={2} maxLength={120} autoComplete="off" />
      </label>
      <label>
        Audience
        <small>Who watches, and where. You can leave this until after the research.</small>
        <textarea name="audience" maxLength={400} />
      </label>
      <label>
        Feeling
        <small>The one thing they should feel at the end.</small>
        <textarea name="feeling" maxLength={400} />
      </label>
      <label>
        Narration languages
        <small>Language codes separated by commas, such as en, am. The first is the main one.</small>
        <input name="languages" defaultValue="en" required autoComplete="off" />
      </label>
      {problem && (
        <p className="problem" role="alert">
          {problem}
        </p>
      )}
      <button type="submit" disabled={busy}>
        {busy ? "Starting the film" : "Start the film"}
      </button>
    </form>
  );
}
