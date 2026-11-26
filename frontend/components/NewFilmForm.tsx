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
          languages: [field("language")],
          story: field("story"),
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
        <small>A person, place or story. Without a story below, it must match the name of a Wikipedia article.</small>
        <input name="title" required minLength={2} maxLength={120} autoComplete="off" />
      </label>
      <label>
        Tell the story yourself
        <small>
          For a story that is not on Wikipedia, such as one from your own family. Write at least 80 words, with the
          names, places and dates you want in the film: the narration may only use what you write here. Leave it
          empty to have the title researched instead.
        </small>
        <textarea name="story" className="tall" maxLength={8000} />
        <small>
          What you write is saved in this repo and sent to the language model. If the story is about real people,
          they must agree to it before the film is shared; faces are never shown unless you record their consent.
        </small>
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
        Narration language
        <small>The film is narrated in this language, with English subtitles.</small>
        <select name="language" defaultValue="en">
          <option value="en">English</option>
          <option value="am">Amharic</option>
          <option value="om">Afaan Oromo</option>
          <option value="ti">Tigrinya</option>
          <option value="so">Somali</option>
        </select>
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
