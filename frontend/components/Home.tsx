"use client";

import Link from "next/link";
import { useLive } from "@/lib/useLive";
import type { FilmSummary, RepoState } from "@/lib/types";
import { NewFilmForm } from "./NewFilmForm";

function where(film: FilmSummary): string {
  if (!film.current) return `All ${film.total} stages are done.`;
  const lead = film.current.who === "you" ? "Your turn:" : film.current.status === "blocked" ? "Blocked at" : "Up next:";
  return `${lead} ${film.current.name}. ${film.done} of ${film.total} stages done.`;
}

const LANGUAGES: Record<string, string> = { en: "English", am: "Amharic", om: "Afaan Oromo", ti: "Tigrinya", so: "Somali" };

function FilmRow({ film }: { film: FilmSummary }) {
  const spoken = film.languages.map((code) => LANGUAGES[code] ?? code).join(", ");
  return (
    <li>
      <Link className="film-row" href={`/films/${film.slug}${film.has_film ? "?stage=assembly" : ""}`}>
        {film.poster ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img className="poster" src={`/api/films/${film.slug}/media/${film.poster.path}?v=${film.poster.v}`} alt="" loading="lazy" />
        ) : (
          <div className="poster none" aria-hidden="true" />
        )}
        <div className="about">
          <span className="film-title">{film.title}</span>
          <span className="quiet">{[film.description, spoken && `Narrated in ${spoken}`].filter(Boolean).join(". ")}</span>
          <span className="where">{where(film)}</span>
        </div>
        <ol className="strip mini" aria-hidden="true">
          {film.stages.map((stage) => (
            <li key={stage.id} className={`frame ${stage.status}`} title={stage.name} />
          ))}
        </ol>
      </Link>
    </li>
  );
}

export function Home({ initial }: { initial: RepoState }) {
  const { value: state, problem } = useLive<RepoState>("/api/films", initial);
  const written = state.docs.filter((doc) => doc.exists).length;

  return (
    <>
      {problem && <p className="fail">The board lost touch with the repo: {problem}</p>}
      <header className="wrap masthead">
        <h1>Films</h1>
        <p>
          Each film starts as a title. Agents research it and draft a storyboard, you direct it, and the pipeline
          renders it. This page reads the repo every five seconds.
        </p>
      </header>

      <main className="wrap">
        {state.films.length ? (
          <ul className="films">
            {state.films.map((film) => (
              <FilmRow key={film.slug} film={film} />
            ))}
          </ul>
        ) : (
          <p className="empty">No films yet. Start one below with a title.</p>
        )}

        <NewFilmForm />

        <section className="paperwork">
          <h2>Paperwork for the whole repo</h2>
          <p className="lede">
            These documents cover every film. {written} of {state.docs.length} are written.
          </p>
          <ul className="checks">
            {state.docs.map((doc) => (
              <li key={doc.name}>
                <span className={doc.exists ? "ok" : "bad"}>{doc.exists ? "Written" : "Missing"}</span>
                <span>{doc.name}</span>
                <span className="quiet">{doc.purpose}</span>
              </li>
            ))}
          </ul>

          <h3>
            Experiments: {state.experiments.titles.length} of {state.experiments.target}
          </h3>
          <Titles titles={state.experiments.titles} />

          <h3>Failures recorded: {state.failures.titles.length}</h3>
          <Titles titles={state.failures.titles} />

          <h3>Who does what</h3>
          <dl className="roles">
          <div>
            <dt className="who you">You</dt>
            <dd>
              You are the director. You choose the story, the audience and the feeling, and you approve or rewrite
              everything the agents draft.
            </dd>
          </div>
          <div>
            <dt className="who agent">Agents</dt>
            <dd>
              Language models that research the title and draft the storyboard. They may only use facts that quote a
              source.
            </dd>
          </div>
          <div>
            <dt className="who code">Code</dt>
            <dd>
              The pipeline. It turns the approved storyboard into pictures, video, voice, music and the final edit,
              and makes no creative choices.
            </dd>
          </div>
          </dl>
        </section>
      </main>
    </>
  );
}

function Titles({ titles }: { titles: string[] }) {
  if (!titles.length) return <p className="quiet">None written yet.</p>;
  return (
    <ul className="titles">
      {titles.map((title) => (
        <li key={title}>{title}</li>
      ))}
    </ul>
  );
}
