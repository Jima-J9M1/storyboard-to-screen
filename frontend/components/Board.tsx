"use client";

import { useEffect, useState } from "react";
import { useLive } from "@/lib/useLive";
import type { FilmState, MediaFile, Stage, Who } from "@/lib/types";

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;
const clock = (ts: string) =>
  new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

// The address of a generated file. The version makes the browser fetch it again when it changes.
const media = (slug: string, file: MediaFile) => `/api/films/${slug}/media/${file.path}?v=${file.v}`;
const megabytes = (file: MediaFile) => `${(file.bytes / 1_000_000).toFixed(1)} MB`;

const LANGUAGES: Record<string, string> = { en: "English", am: "Amharic", om: "Afaan Oromo", ti: "Tigrinya", so: "Somali" };

const WHO: Record<Who, string> = { you: "You", agent: "Agents", code: "Code" };

function frameLabel(stage: Stage): string {
  if (stage.status === "done") return "Done";
  if (!stage.current) return "Waiting";
  return stage.status === "blocked" ? "Blocked" : "Up next";
}

export function Board({ initial, stage }: { initial: FilmState; stage?: string }) {
  const { value: film, problem } = useLive<FilmState>(`/api/films/${initial.slug}`, initial);
  const [picked, setPicked] = useState<string | null>(stage ?? null);

  // Keep the chosen stage in the address, so a refresh or a shared link opens the same stage.
  function pick(id: string) {
    setPicked(id);
    window.history.replaceState(null, "", `?stage=${id}`);
  }

  const brief = film.brief ?? {};
  const current = film.stages.find((stage) => stage.current);
  const done = film.stages.filter((stage) => stage.done).length;
  // The stage on show: the one the director clicked, otherwise the one the film is at.
  const shown = film.stages.find((stage) => stage.id === picked) ?? current ?? film.stages[film.stages.length - 1];

  return (
    <>
      {problem && <p className="fail">The board lost touch with the repo: {problem}</p>}

      <header className="wrap top">
        <div>
          <h1 className="film-name">{brief.title || film.slug}</h1>
          <p className="film-kind">
            {[film.research.subject?.description, brief.languages && `Narrated in ${brief.languages.map((code) => LANGUAGES[code] ?? code).join(", ")}`]
              .filter(Boolean)
              .join(". ")}
          </p>
        </div>
        <div className="progress">
          <p>
            {current
              ? `${done} of ${film.stages.length} stages are done. The film is at ${current.name}.`
              : `All ${film.stages.length} stages are done.`}{" "}
            Choose a stage to see what it made.
          </p>
          {Object.keys(film.outputs.film.shapes).length > 0 && shown.id !== "assembly" && (
            <button type="button" className="watch" onClick={() => pick("assembly")}>
              Watch the film
            </button>
          )}
        </div>
      </header>

      <div className="strip-scroll">
        <ol className="strip full" aria-label="Production stages. Choose one to see what it made.">
          {film.stages.map((stage) => (
            <li key={stage.id}>
              <button
                type="button"
                className={`frame ${stage.status}`}
                aria-pressed={stage.id === shown.id}
                aria-current={stage.current ? "step" : undefined}
                onClick={() => pick(stage.id)}
              >
                <b>{stage.name}</b>
                <span className={`who ${stage.who}`}>{WHO[stage.who]}</span>
                <span>{frameLabel(stage)}</span>
              </button>
            </li>
          ))}
        </ol>
      </div>

      <section className="now" aria-live="polite">
        <div className="wrap">
          <div className="stage-head">
            <h2>{shown.name}</h2>
            <p>
              <span className={`pill ${shown.status}`}>{frameLabel(shown)}</span>
              <span className={`who ${shown.who}`}>{shown.who_label}</span>
            </p>
          </div>
          <dl className="stage-guide">
            <div>
              <dt>What happens here</dt>
              <dd>{shown.what}</dd>
            </div>
            <div>
              <dt>Your part as director</dt>
              <dd>{shown.your_part}</dd>
            </div>
            <div>
              <dt>Right now</dt>
              <dd>
                {shown.detail}
                {shown.problems.length > 0 && (
                  <ul className="problems">
                    {shown.problems.map((p) => (
                      <li key={p}>{p}</li>
                    ))}
                  </ul>
                )}
                {shown.command && (
                  <span className="do">
                    {shown.done ? "Run it again" : "Run it"} in the terminal: <code>{shown.command}</code>
                  </span>
                )}
              </dd>
            </div>
          </dl>
        </div>
      </section>

      <main className="wrap">
        <section className="panel">
          <h3 className="made">What {shown.name} made</h3>
          <StageOutput stage={shown} film={film} />
          <StageCalls stage={shown} film={film} />
        </section>
        <p className="foot">Read from the repo every five seconds. This page changes nothing.</p>
      </main>
    </>
  );
}

// ---------- what each stage made ----------

function StageOutput({ stage, film }: { stage: Stage; film: FilmState }) {
  switch (stage.id) {
    case "intent":
      return <IntentOutput film={film} />;
    case "research":
      return <ResearchOutput film={film} />;
    case "script":
      return <ScriptOutput film={film} />;
    case "radio_cut":
      return <RadioCutOutput film={film} />;
    case "keyframes":
      return <PicturesOutput film={film} />;
    case "shots":
      return <ShotsOutput film={film} />;
    case "music":
      return <MusicOutput film={film} />;
    case "narration":
      return <VoiceOutput film={film} />;
    default:
      return <EditOutput film={film} />;
  }
}

const Nothing = ({ children }: { children: React.ReactNode }) => <p className="empty">{children}</p>;

function IntentOutput({ film }: { film: FilmState }) {
  const brief = film.brief ?? {};
  const row = (label: string, value?: string) => (
    <div>
      <dt>{label}</dt>
      {value ? <dd>{value}</dd> : <dd className="bad">Not written yet.</dd>}
    </div>
  );
  return (
    <>
      <p className="lede">
        The brief, in <code>films/{film.slug}/brief.json</code>. Every agent reads it.
      </p>
      <dl className="brief">
        {row("Title", brief.title)}
        {row("Audience", brief.audience)}
        {row("Feeling", brief.feeling)}
        {row("Languages", brief.languages?.join(", "))}
      </dl>
    </>
  );
}

function ResearchOutput({ film }: { film: FilmState }) {
  const { subject, sources, facts, facts_model } = film.research;
  const guarded = subject?.likeness_policy && subject.likeness_policy !== "unrestricted";
  if (facts.length === 0) return <Nothing>No facts yet.</Nothing>;
  return (
    <>
      {guarded && (
        <div className="notice">
          <strong>
            {subject.likeness_policy === "no_likeness"
              ? "This person must not be shown or voiced"
              : "A person decides how this subject is shown"}
          </strong>
          {subject.policy_reason}
        </div>
      )}
      <h4>Sources read</h4>
      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th>Source</th>
              <th>Page</th>
              <th className="num">Words</th>
              <th>Licence</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((src) => (
              <tr key={src.source_id}>
                <td>{src.source_id}</td>
                <td>
                  <a href={src.url} target="_blank" rel="noopener noreferrer">
                    {src.title || src.url}
                  </a>
                </td>
                <td className="num">{src.words}</td>
                <td className="quiet">{src.licence}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h4>Facts found</h4>
      <p className="lede">
        {plural(facts.length, "fact")}, listed by {facts_model}. Each one quotes its source word for word, and the quote
        was checked by code. The narration may only use these.
      </p>
      <ol className="facts">
        {facts.map((fact) => (
          <li key={fact.id}>
            <span className="id">{fact.id}</span>
            <div>
              {fact.text}
              <details>
                <summary>Show the source&rsquo;s words</summary>
                <blockquote>{fact.quote}</blockquote>
              </details>
            </div>
            <span className="src">{fact.source_id}</span>
          </li>
        ))}
      </ol>
    </>
  );
}

function ScriptOutput({ film }: { film: FilmState }) {
  const board = film.storyboard;
  if (!board) {
    return (
      <Nothing>
        {film.stages.find((s) => s.id === "script")?.problems.length
          ? "storyboard.json exists but does not pass validation. The problems are listed above."
          : "No storyboard yet."}
      </Nothing>
    );
  }
  const language = board.languages[0];
  const total = board.shots.reduce((sum, shot) => sum + shot.duration_s, 0) + board.end_card.duration_s;
  const words = board.shots.reduce(
    (sum, shot) => sum + (shot.narration[language] || "").split(/\s+/).filter(Boolean).length,
    0,
  );
  return (
    <>
      <p className="lede">
        The storyboard, in <code>films/{film.slug}/storyboard.json</code>: {plural(board.shots.length, "shot")}, {words}{" "}
        words, {total} seconds with the end card. It is yours to edit.
      </p>
      <dl className="brief">
        <div>
          <dt>Look</dt>
          <dd>{board.style_block}</dd>
        </div>
        <div>
          <dt>Narrator</dt>
          <dd>
            Voice &ldquo;{board.voice.name}&rdquo;, {board.voice.style}
          </dd>
        </div>
        <div>
          <dt>Score brief</dt>
          <dd>
            {board.music.caption} {board.music.bpm} bpm, {board.music.key}.
          </dd>
        </div>
        <div>
          <dt>End card</dt>
          <dd>{board.end_card.text}</dd>
        </div>
      </dl>
      <h4>Shots</h4>
      <ol className="script">
        {board.shots.map((shot) => (
          <li key={shot.id}>
            <div className="slate">
              <b>{shot.id}</b>
              {shot.duration_s} s<br />
              {shot.size}
            </div>
            <div className="body">
              <div className="line" lang={language}>
                {shot.narration[language] || "No narration"}
              </div>
              {language !== "en" && <p className="sub">English subtitle: {shot.subtitle_en}</p>}
              <dl className="facts-of-shot">
                <div>
                  <dt>Why</dt>
                  <dd>{shot.reason}</dd>
                </div>
                <div>
                  <dt>Picture</dt>
                  <dd>{shot.image_prompt}</dd>
                </div>
                <div>
                  <dt>Motion</dt>
                  <dd>{shot.motion_prompt}</dd>
                </div>
                <div>
                  <dt>Facts used</dt>
                  <dd>{shot.fact_ids.join(", ") || "none"}</dd>
                </div>
              </dl>
            </div>
          </li>
        ))}
      </ol>
    </>
  );
}

function RadioCutOutput({ film }: { film: FilmState }) {
  const cut = film.outputs.radio_cut;
  if (!cut.audio && !cut.video) return <Nothing>No radio cut yet.</Nothing>;
  return (
    <>
      <p className="lede">The narration over placeholder music on a black screen. Send it to your three listeners.</p>
      {cut.audio && (
        <div className="file">
          <audio controls preload="none" src={media(film.slug, cut.audio)} />
          <span className="quiet">
            radio_cut.m4a, {megabytes(cut.audio)}.{" "}
            <a href={media(film.slug, cut.audio)} download="radio_cut.m4a">
              Download
            </a>
          </span>
        </div>
      )}
      {cut.video && (
        <p className="quiet">
          With a black screen: radio_cut.mp4, {megabytes(cut.video)}.{" "}
          <a href={media(film.slug, cut.video)} download="radio_cut.mp4">
            Download
          </a>
        </p>
      )}
    </>
  );
}

type Picture = { file: MediaFile; title: string; text: string };

function PicturesOutput({ film }: { film: FilmState }) {
  const out = film.outputs;
  const shots = film.storyboard?.shots ?? [];
  const [open, setOpen] = useState<number | null>(null);

  const pictures: Picture[] = [];
  if (out.reference) {
    pictures.push({ file: out.reference, title: "Reference sheet", text: film.storyboard?.reference_sheet.prompt ?? "" });
  }
  const missing: string[] = [];
  for (const shot of shots) {
    const picture = out.shots[shot.id]?.picture;
    if (!picture) {
      missing.push(shot.id);
      continue;
    }
    pictures.push({
      file: picture,
      title: `${shot.id}, seed ${shot.seed}, ${shot.use_reference ? "guided by the reference sheet" : "style description only"}`,
      text: shot.image_prompt,
    });
  }
  if (pictures.length === 0) return <Nothing>No pictures yet.</Nothing>;

  return (
    <>
      <p className="lede">
        The reference sheet fixes the look. Then one picture per shot, each painted from the description under it.
        Choose a picture to see it large.
      </p>
      {film.storyboard && (
        <dl className="brief">
          <div>
            <dt>Who and where</dt>
            <dd>{film.storyboard.world_block}</dd>
          </div>
          <div>
            <dt>Look</dt>
            <dd>{film.storyboard.style_block}</dd>
          </div>
        </dl>
      )}
      <ul className="gallery">
        {pictures.map((picture, n) => (
          <li key={picture.file.path}>
            <button type="button" className="open" onClick={() => setOpen(n)} aria-label={`Open ${picture.title}`}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={media(film.slug, picture.file)} alt="" loading="lazy" />
            </button>
            <b>{picture.title}</b>
            <span>{picture.text}</span>
          </li>
        ))}
      </ul>
      {missing.length > 0 && <p className="quiet">Not made yet: {missing.join(", ")}.</p>}
      {open !== null && pictures[open] && (
        <Viewer slug={film.slug} pictures={pictures} at={open} go={setOpen} />
      )}
    </>
  );
}

function Viewer({ slug, pictures, at, go }: { slug: string; pictures: Picture[]; at: number; go: (n: number | null) => void }) {
  const picture = pictures[at];
  const step = (by: number) => go((at + by + pictures.length) % pictures.length);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") go(null);
      if (event.key === "ArrowRight") step(1);
      if (event.key === "ArrowLeft") step(-1);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });
  return (
    <div className="viewer" role="dialog" aria-modal="true" aria-label={picture.title} onClick={() => go(null)}>
      <figure onClick={(event) => event.stopPropagation()}>
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={media(slug, picture.file)} alt={picture.text} />
        <figcaption>
          <b>{picture.title}</b>
          {picture.text}
        </figcaption>
        <div className="viewer-keys">
          <button type="button" onClick={() => step(-1)}>
            Previous
          </button>
          <span>
            {at + 1} of {pictures.length}
          </span>
          <button type="button" onClick={() => step(1)}>
            Next
          </button>
          <button type="button" onClick={() => go(null)} autoFocus>
            Close
          </button>
        </div>
      </figure>
    </div>
  );
}

function ShotsOutput({ film }: { film: FilmState }) {
  const shots = film.storyboard?.shots ?? [];
  const made = shots.filter((shot) => film.outputs.shots[shot.id]?.clips["9x16"]);
  if (made.length === 0) return <Nothing>No clips yet.</Nothing>;
  return (
    <>
      <p className="lede">
        One clip per shot: a slow camera move over its picture. Each exists tall (shown here) and wide. Press play on any
        of them.
      </p>
      <ul className="gallery clips">
        {shots.map((shot) => {
          const output = film.outputs.shots[shot.id];
          const tall = output?.clips["9x16"];
          const wide = output?.clips["16x9"];
          return (
            <li key={shot.id}>
              {tall ? (
                <video controls preload="metadata" src={media(film.slug, tall)} />
              ) : (
                <div className="none">Not made yet</div>
              )}
              <b>
                {shot.id}, {shot.duration_s} s
              </b>
              <span className={output?.move?.includes("generated") ? "ok" : undefined}>
                {output?.move ?? "Not made yet"}
              </span>
              <span>Asked for: {shot.motion_prompt}</span>
              {wide && (
                <a href={media(film.slug, wide)} target="_blank" rel="noreferrer">
                  Play the wide clip
                </a>
              )}
            </li>
          );
        })}
      </ul>
    </>
  );
}

function MusicOutput({ film }: { film: FilmState }) {
  const music = film.outputs.music;
  const brief = film.storyboard?.music;
  return (
    <>
      {brief && (
        <dl className="brief">
          <div>
            <dt>Asked for</dt>
            <dd>
              {brief.caption} {brief.bpm} bpm, {brief.key}. One candidate for each seed: {brief.seeds.join(", ")}.
            </dd>
          </div>
        </dl>
      )}
      {music.candidates.length === 0 ? (
        <Nothing>
          No score candidates yet. They are generated on a Kaggle GPU, which can wait in a queue before it starts.
        </Nothing>
      ) : (
        <>
          <p className="lede">
            Three candidates from the same brief. Judge each one under the narration, which is how it sits in the film,
            then write the seed you choose into the storyboard as <code>chosen_seed</code>.
            {music.gpu_seconds != null && ` Made in ${(music.gpu_seconds / 60).toFixed(1)} GPU minutes on a ${music.gpu}.`}
          </p>
          <div className="scroll">
            <table className="candidates">
              <thead>
                <tr>
                  <th>Candidate</th>
                  <th>Under the narration</th>
                  <th>The score alone</th>
                </tr>
              </thead>
              <tbody>
                {music.candidates.map((candidate) => (
                  <tr key={candidate.seed}>
                    <td>
                      Seed {candidate.seed}
                      {candidate.seed === music.chosen_seed && <b className="ok"> chosen</b>}
                      {candidate.seconds_to_make != null && (
                        <span className="quiet">
                          <br />
                          made in {candidate.seconds_to_make} s
                        </span>
                      )}
                    </td>
                    <td>
                      {candidate.audition ? (
                        <audio controls preload="none" src={media(film.slug, candidate.audition)} />
                      ) : (
                        <span className="quiet">Needs the voice first</span>
                      )}
                    </td>
                    <td>
                      <audio controls preload="none" src={media(film.slug, candidate)} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  );
}

function VoiceOutput({ film }: { film: FilmState }) {
  const board = film.storyboard;
  const language = board?.languages[0] ?? "en";
  const shots = board?.shots ?? [];
  const spoken = shots.filter((shot) => film.outputs.shots[shot.id]?.narration[language]);
  if (spoken.length === 0) return <Nothing>No narration audio yet.</Nothing>;
  return (
    <>
      <p className="lede">
        One audio file per shot. Each was measured, and written down by a model to check it says its line and nothing
        else.
      </p>
      <ol className="voice">
        {shots.map((shot) => {
          const voice = film.outputs.shots[shot.id]?.narration[language];
          const wrong = voice && (voice.fits === false || voice.matches_line === false);
          return (
            <li key={shot.id}>
              <span className="id">{shot.id}</span>
              <div>
                <div className="line" lang={language}>
                  {shot.narration[language] || "No narration"}
                </div>
                {language !== "en" && <p className="sub">English subtitle: {shot.subtitle_en}</p>}
                {voice ? (
                  <>
                    <audio controls preload="none" src={media(film.slug, voice)} />
                    <p className={wrong ? "pic bad" : "pic"}>
                      {voice.spoken_s} s spoken, in a {shot.duration_s} s shot. Voice model: {voice.model}.{" "}
                      {voice.fits === false && "Longer than its shot. "}
                      {voice.matches_line === false
                        ? `The recording says: "${voice.heard}"`
                        : "The recording matches the line."}
                    </p>
                  </>
                ) : (
                  <p className="pic">Not spoken yet.</p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
    </>
  );
}

function EditOutput({ film }: { film: FilmState }) {
  const out = film.outputs.film;
  const shapes = Object.entries(out.shapes);
  const names: Record<string, string> = { "9x16": "Tall, for phones", "16x9": "Wide" };
  if (shapes.length === 0) return <Nothing>No film yet.</Nothing>;
  return (
    <>
      {out.placeholder_music && (
        <div className="notice">
          <strong>This is a rough cut</strong>
          The music is a placeholder chord. It becomes the real score once a candidate is chosen.
        </div>
      )}
      <div className="exports">
        {shapes.map(([shape, file]) => (
          <figure key={shape} className={`player s${shape}`}>
            <video controls preload="metadata" src={media(film.slug, file)} />
            <figcaption>
              <b>{names[shape] ?? shape}</b>
              {file.duration_s} s, {file.loudness_lufs} LUFS, peak {file.true_peak_db} dB,{" "}
              {plural(file.subtitle_cards, "subtitle card")}, {megabytes(file)}
              <br />
              <a href={media(film.slug, file)} download={file.path.split("/").pop()}>
                Download
              </a>
            </figcaption>
          </figure>
        ))}
      </div>
    </>
  );
}

// ---------- the outside calls a stage made ----------

function StageCalls({ stage, film }: { stage: Stage; film: FilmState }) {
  const calls = stage.calls;
  if (!calls) {
    return (
      <p className="quiet calls-note">
        {stage.id === "intent"
          ? "This stage is written by you. It calls no model."
          : "This stage runs in FFmpeg on your machine. It calls no model, so it has no entries in the run log."}
      </p>
    );
  }
  if (calls.attempts === 0) return <p className="quiet calls-note">No calls made yet.</p>;
  const mine = film.runs.recent.filter((run) => run.stage === calls.log_name);
  return (
    <details className="calls">
      <summary>
        {plural(calls.attempts, "call")} to outside services: {calls.ok} succeeded, {calls.failed} failed
      </summary>
      <p className="quiet">
        {calls.seconds} seconds in successful calls. Answered by: {calls.models.join(", ") || "none"}.
      </p>
      <div className="scroll">
        <table>
          <thead>
            <tr>
              <th>Time</th>
              <th>Item</th>
              <th>Service</th>
              <th className="num">Try</th>
              <th>Result</th>
              <th className="num">Took</th>
            </tr>
          </thead>
          <tbody>
            {mine.map((run, n) => (
              <tr key={`${run.ts}-${run.model}-${run.attempt}-${n}`}>
                <td className="quiet">{clock(run.ts)}</td>
                <td>{run.item}</td>
                <td>{run.model}</td>
                <td className="num">{run.attempt}</td>
                <td className={run.status === "ok" ? "ok" : "bad"}>
                  {run.status === "ok" ? "Succeeded" : `Failed: ${run.error}`}
                </td>
                <td className="num">{run.latency_s} s</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}
