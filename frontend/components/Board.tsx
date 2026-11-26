"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useLive } from "@/lib/useLive";
import type { FilmState, MediaFile, Stage, Who } from "@/lib/types";
import { Direct } from "./Direct";
import { RunStage } from "./RunStage";

const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;
const clock = (ts: string) =>
  new Date(ts).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });

// The address of a generated file. The version makes the browser fetch it again when it changes.
const media = (slug: string, file: MediaFile) => `/api/films/${slug}/media/${file.path}?v=${file.v}`;
const megabytes = (file: MediaFile) => `${(file.bytes / 1_000_000).toFixed(1)} MB`;

const LANGUAGES: Record<string, string> = { en: "English", am: "Amharic", om: "Afaan Oromo", ti: "Tigrinya", so: "Somali" };

const runtime = (seconds: number) => `${Math.floor(seconds / 60)} min ${Math.round(seconds % 60)} s`;

const WHO: Record<Who, string> = { you: "You", agent: "Agents", code: "Code" };

function frameLabel(stage: Stage): string {
  if (stage.status === "done") return "Done";
  if (!stage.current) return "Waiting";
  return stage.status === "blocked" ? "Blocked" : "Up next";
}

export function Board({ initial, stage }: { initial: FilmState; stage?: string }) {
  const { value: film, problem } = useLive<FilmState>(`/api/films/${initial.slug}`, initial);
  const [picked, setPicked] = useState<string | null>(stage ?? null);
  const [theatre, setTheatre] = useState(false);

  // Keep the chosen stage in the address, so a refresh or a shared link opens the same stage.
  function pick(id: string) {
    setPicked(id);
    window.history.replaceState(null, "", `?stage=${id}`);
  }

  const brief = film.brief ?? {};
  const hasFilm = Object.keys(film.outputs.film.shapes).length > 0;
  const current = film.stages.find((stage) => stage.current);
  const done = film.stages.filter((stage) => stage.done).length;
  // What is on show: the director's choice; otherwise the film if there is one, otherwise the stage it is at.
  const view = picked ?? (hasFilm ? "film" : (current ?? film.stages[0]).id);
  const shown = film.stages.find((stage) => stage.id === view) ?? current ?? film.stages[film.stages.length - 1];

  return (
    <>
      {problem && <p className="fail">The board lost touch with the repo: {problem}</p>}

      <header className="hero">
        {film.backdrop && (
          // eslint-disable-next-line @next/next/no-img-element
          <img className="hero-backdrop" src={media(film.slug, film.backdrop)} alt="" />
        )}
        <div className="wrap hero-inner">
          <Link className="back" href="/">
            All films
          </Link>
          <h1 className="film-name">{brief.title || film.slug}</h1>
          <ul className="meta">
            {film.runtime_s != null && <li>{runtime(film.runtime_s)}</li>}
            {brief.languages && (
              <li>Narrated in {brief.languages.map((code) => LANGUAGES[code] ?? code).join(", ")}</li>
            )}
            {film.storyboard && <li>English subtitles</li>}
            {film.storyboard && <li>{plural(film.storyboard.shots.length, "shot")}</li>}
            <li className={hasFilm && !film.outputs.film.placeholder_music ? "tag done" : "tag"}>
              {!hasFilm ? `${done} of ${film.stages.length} stages done` : film.outputs.film.placeholder_music ? "Rough cut" : "Finished"}
            </li>
          </ul>
          {film.research.subject?.description && <p className="film-kind">{film.research.subject.description}</p>}
          {brief.feeling && <p className="logline">{brief.feeling}</p>}
          <div className="hero-keys">
            {hasFilm && (
              <button type="button" className="watch" onClick={() => setTheatre(true)}>
                Watch the film
              </button>
            )}
            <a className="how" href="#stages">
              {current ? `See the stages. It is at ${current.name}.` : "See how it was made"}
            </a>
          </div>
        </div>
      </header>

      {theatre && hasFilm && <Theatre film={film} close={() => setTheatre(false)} />}

      <div className="wrap workspace" id="stages">
        <nav className="pipeline" aria-label="The film and the stages that made it">
          <button type="button" className="pipe-film" aria-pressed={view === "film"} onClick={() => pick("film")}>
            <b>The film</b>
            <span>{!hasFilm ? "Not cut yet" : film.outputs.film.placeholder_music ? "Rough cut" : "Finished"}</span>
          </button>
          <p className="pipe-title">How it is made</p>
          <ol>
            {film.stages.map((stage, n) => (
              <li key={stage.id} className={stage.status}>
                <button
                  type="button"
                  aria-pressed={view === stage.id}
                  aria-current={stage.current ? "step" : undefined}
                  onClick={() => pick(stage.id)}
                >
                  <i aria-hidden="true">{n + 1}</i>
                  <span>
                    <b>{stage.name}</b>
                    <small>
                      {WHO[stage.who]}, {frameLabel(stage).toLowerCase()}
                    </small>
                  </span>
                </button>
              </li>
            ))}
          </ol>
          <button type="button" className="pipe-notes" aria-pressed={view === "notes"} onClick={() => pick("notes")}>
            Your notes
            <span>{film.direction.length}</span>
          </button>
        </nav>

        <main className="stage-view" aria-live="polite">
          {view === "film" ? (
            <FinalOutput film={film} watch={() => setTheatre(true)} />
          ) : view === "notes" ? (
            <NotesView film={film} />
          ) : (
            <>
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
              {shown.runnable && (
                <RunStage
                  key={shown.id}
                  slug={film.slug}
                  stage={shown.id}
                  busy={film.running}
                  label={shown.done ? `Run ${shown.name} again` : `Run ${shown.name} now`}
                />
              )}
              <h3 className="made">What {shown.name} made</h3>
              <StageOutput stage={shown} film={film} />
              <StageCalls stage={shown} film={film} />
            </>
          )}
          <p className="foot">Read from the repo every five seconds.</p>
        </main>
      </div>
    </>
  );
}

// ---------- watching the film ----------

function Theatre({ film, close }: { film: FilmState; close: () => void }) {
  const shapes = film.outputs.film.shapes;
  const [shape, setShape] = useState(shapes["16x9"] ? "16x9" : Object.keys(shapes)[0]);
  const names: Record<string, string> = { "9x16": "Tall", "16x9": "Wide" };
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && close();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });
  const file = shapes[shape];
  return (
    <div className="theatre" role="dialog" aria-modal="true" aria-label={`${film.brief?.title ?? film.slug}, the film`} onClick={close}>
      <div className={`screen s${shape}`} onClick={(event) => event.stopPropagation()}>
        <video key={file.path + file.v} controls autoPlay src={media(film.slug, file)} />
        <div className="theatre-keys">
          {Object.keys(shapes).map((name) => (
            <button key={name} type="button" aria-pressed={name === shape} onClick={() => setShape(name)}>
              {names[name] ?? name}
            </button>
          ))}
          <span>
            {film.outputs.film.placeholder_music ? "Rough cut: placeholder music. " : ""}
            {film.film_is_stale ? "Older than its storyboard." : ""}
          </span>
          <button type="button" onClick={close}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// ---------- the finished film ----------

function FinalOutput({ film, watch }: { film: FilmState; watch: () => void }) {
  const out = film.outputs.film;
  const shapes = out.shapes;
  const board = film.storyboard;
  const names: Record<string, string> = { "9x16": "Tall, for phones", "16x9": "Wide" };
  const [shape, setShape] = useState(shapes["9x16"] ? "9x16" : Object.keys(shapes)[0]);
  const [at, setAt] = useState(0);
  const [player, setPlayer] = useState<HTMLVideoElement | null>(null);

  if (Object.keys(shapes).length === 0 || !board) {
    return (
      <>
        <div className="stage-head">
          <h2>The film</h2>
        </div>
        <Nothing>
          No film has been cut yet. It is made by <code>make film FILM={film.slug}</code> once the stages on the left
          are done.
        </Nothing>
      </>
    );
  }

  // Where each shot starts, so the timeline can jump the player to it.
  const language = board.languages[0];
  let clock = 0;
  const timeline = board.shots.map((shot) => {
    const entry = { shot, start: clock, picture: film.outputs.shots[shot.id]?.picture ?? null };
    clock += shot.duration_s;
    return entry;
  });
  const total = clock + board.end_card.duration_s;
  const playing = [...timeline].reverse().find((entry) => at >= entry.start - 0.05) ?? timeline[0];
  const onEndCard = at >= clock;
  const file = shapes[shape];
  const passed = film.release_checks.filter((check) => check.pass).length;
  const jump = (seconds: number) => {
    if (!player) return;
    player.currentTime = seconds + 0.05;
    void player.play();
  };

  return (
    <>
      <div className="stage-head">
        <h2>The film</h2>
        <p>
          <span className={`pill ${out.placeholder_music ? "ready" : "done"}`}>{out.placeholder_music ? "Rough cut" : "Finished"}</span>
          <span className="quiet">
            {runtime(file.duration_s)}, {plural(board.shots.length, "shot")}
          </span>
        </p>
      </div>
      {film.film_is_stale && (
        <div className="notice">
          <strong>This film is older than its storyboard</strong>
          Something was changed after it was cut. Run <code>make film FILM={film.slug}</code> to cut it again.
        </div>
      )}
      {out.placeholder_music && (
        <div className="notice">
          <strong>The music is a placeholder</strong>
          Choose one of the score candidates on the Music stage, then cut the film again.
        </div>
      )}

      <div className={`final s${shape}`}>
        <div className="final-screen">
          <video
            key={file.path + file.v}
            ref={setPlayer}
            controls
            preload="metadata"
            src={media(film.slug, file)}
            onTimeUpdate={(event) => setAt(event.currentTarget.currentTime)}
          />
        </div>
        <div className="final-side">
          <div className="switch" role="group" aria-label="Shape of the film">
            {Object.keys(shapes).map((name) => (
              <button key={name} type="button" aria-pressed={name === shape} onClick={() => setShape(name)}>
                {names[name] ?? name}
              </button>
            ))}
            <button type="button" onClick={watch}>
              Full screen
            </button>
          </div>
          <div className="now-playing">
            <span className="quiet">{onEndCard ? "End card" : `On screen now: ${playing.shot.id}`}</span>
            <p className="line" lang={language}>
              {onEndCard ? board.end_card.text : playing.shot.narration[language]}
            </p>
            {!onEndCard && language !== "en" && <p className="sub">{playing.shot.subtitle_en}</p>}
            {!onEndCard && <p className="pic">{playing.shot.reason}</p>}
          </div>
          <ul className="downloads">
            {Object.entries(shapes).map(([name, item]) => (
              <li key={name}>
                <a href={media(film.slug, item)} download={item.path.split("/").pop()}>
                  Download the {name === "9x16" ? "tall" : "wide"} film
                </a>
                <span className="quiet"> {megabytes(item)}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>

      <h3>Shot by shot</h3>
      <p className="lede">Each block is one shot, as wide as it is long. Choose one to play the film from there.</p>
      <ol className="timeline" style={{ gridTemplateColumns: timeline.map((entry) => `${entry.shot.duration_s}fr`).join(" ") + ` ${board.end_card.duration_s}fr` }}>
        {timeline.map((entry) => (
          <li key={entry.shot.id}>
            <button
              type="button"
              aria-pressed={!onEndCard && playing.shot.id === entry.shot.id}
              onClick={() => jump(entry.start)}
              title={entry.shot.subtitle_en}
            >
              {entry.picture && (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={media(film.slug, entry.picture)} alt="" loading="lazy" />
              )}
              <span>{entry.shot.id}</span>
            </button>
          </li>
        ))}
        <li>
          <button type="button" className="end" aria-pressed={onEndCard} onClick={() => jump(clock)} title={board.end_card.text}>
            <span>End</span>
          </button>
        </li>
      </ol>
      <p className="quiet timeline-foot">
        0 s to {total.toFixed(1)} s. The current shot is outlined while the film plays.
      </p>

      <h3>
        Ready to publish: {passed} of {film.release_checks.length} checks pass
      </h3>
      <p className="lede">Each line is what the assignment asks of the film, with the measurement it was checked against.</p>
      <ul className="checks release">
        {film.release_checks.map((check) => (
          <li key={check.label}>
            <span className={check.pass ? "ok" : "bad"}>{check.pass ? "Passes" : "Not yet"}</span>
            <span>{check.label}</span>
            <span className="quiet">{check.detail}</span>
          </li>
        ))}
      </ul>
      <p className="quiet">
        Three things only you can check: that the narration sounds right, that the motion looks right, and that the
        story lands with your audience.
      </p>

      <h3>Credits</h3>
      <dl className="credit-list">
        {film.credits.map((credit) => (
          <div key={credit.role}>
            <dt>{credit.role}</dt>
            <dd>
              {credit.who}
              {credit.note && <span className="quiet"> {credit.note}</span>}
            </dd>
          </div>
        ))}
      </dl>
    </>
  );
}

function NotesView({ film }: { film: FilmState }) {
  return (
    <>
      <div className="stage-head">
        <h2>Your notes</h2>
      </div>
      {film.direction.length === 0 ? (
        <Nothing>
          You have not given a note on this film yet. On the Pictures, Script and Music stages, each item has a button
          for saying what is wrong and how to fix it.
        </Nothing>
      ) : (
        <>
          <p className="lede">
            Every note you have given, newest first, with what the Reviser changed because of it. This is the record
            of your direction.
          </p>
          <ol className="notes">
            {film.direction.map((entry, n) => (
              <li key={`${entry.ts}-${n}`}>
                <b>
                  {DIRECTED[entry.target] ?? entry.target}
                  {entry.shot ? `, ${entry.shot}` : ""}
                </b>
                <span className="quiet"> {new Date(entry.ts).toLocaleString()}</span>
                <p>&ldquo;{entry.note}&rdquo;</p>
                <p className="quiet">{entry.what_changed}</p>
              </li>
            ))}
          </ol>
        </>
      )}
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
  const hasFilm = Object.keys(film.outputs.film.shapes).length > 0;
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
                  {src.url ? (
                    <a href={src.url} target="_blank" rel="noopener noreferrer">
                      {src.title || src.url}
                    </a>
                  ) : (
                    src.title
                  )}
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
              <div className="direct-row">
                <Direct
                  slug={film.slug}
                  target="line"
                  shot={shot.id}
                  label="Change this line"
                  placeholder="What should the narrator say differently? It may only use the facts listed for this shot."
                  waiting="Rewriting and re-recording, about a minute"
                />
                <Direct
                  slug={film.slug}
                  target="motion"
                  shot={shot.id}
                  label="Change the motion"
                  placeholder="What should move, and how should the camera move?"
                  waiting="Rewriting"
                />
              </div>
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

type Picture = { file: MediaFile; title: string; text: string; shot?: string };

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
      shot: shot.id,
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
            {picture.shot && (
              <Direct
                slug={film.slug}
                target="picture"
                shot={picture.shot}
                label="Fix this picture"
                placeholder="What is wrong, and how should it look? For example: there are three hands, show only two."
                waiting="Repainting, about a minute"
                reroll="Just try another version"
              />
            )}
          </li>
        ))}
      </ul>
      <div className="direct-row">
        <Direct
          slug={film.slug}
          target="world"
          label="Change who and where, for every picture"
          placeholder="What is wrong with the people, dress, homes or land across the film?"
          waiting="Repainting every picture, several minutes"
        />
        <Direct
          slug={film.slug}
          target="look"
          label="Change the look of every picture"
          placeholder="How should the style change? For example: less golden, cooler morning light."
          waiting="Repainting every picture, several minutes"
        />
      </div>
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
      <Direct
        slug={film.slug}
        target="score"
        label="Change the score brief"
        placeholder="How should the music be different? For example: slower, with a krar, no strings."
        waiting="Rewriting"
      />
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
          const wrong = voice && (voice.fits === false || (language === "en" && voice.matches_line === false));
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
                      {language !== "en"
                        ? "Not verified: the automatic check is unreliable in this language, so a speaker must listen."
                        : voice.matches_line === false
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
      <VoiceCompare film={film} />
    </>
  );
}

const PROVIDERS: Record<string, string> = { gemini: "Gemini", addis: "Addis AI" };

function VoiceCompare({ film }: { film: FilmState }) {
  const compare = film.outputs.voice_compare;
  const providers = Object.keys(compare);
  const board = film.storyboard;
  if (providers.length < 2 || !board) return null;
  const language = board.languages[0];
  const seconds = (provider: string) =>
    Object.values(compare[provider]).reduce((sum, line) => sum + (line.spoken_s ?? 0), 0);
  return (
    <>
      <h4>The same lines by two voices</h4>
      <p className="lede">
        Listen to each line both ways and decide which narrator the film should have. Judge the pronunciation of names,
        places and numbers: no automatic check can do that for this language.
      </p>
      <div className="scroll">
        <table className="candidates">
          <thead>
            <tr>
              <th>Line</th>
              {providers.map((provider) => (
                <th key={provider}>
                  {PROVIDERS[provider] ?? provider}
                  <span className="quiet">
                    {" "}
                    ({Object.keys(compare[provider]).length} lines, {seconds(provider).toFixed(1)} s)
                  </span>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {board.shots.map((shot) => (
              <tr key={shot.id}>
                <td>
                  <b>{shot.id}</b>
                  <div lang={language}>{shot.narration[language]}</div>
                  <span className="quiet">{shot.subtitle_en}</span>
                </td>
                {providers.map((provider) => {
                  const line = compare[provider][shot.id];
                  return (
                    <td key={provider}>
                      {line ? (
                        <>
                          <audio controls preload="none" src={media(film.slug, line)} />
                          <span className="quiet">{line.spoken_s} s</span>
                        </>
                      ) : (
                        <span className="quiet">Not recorded</span>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
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
      {film.film_is_stale && (
        <div className="notice">
          <strong>This film is older than its storyboard</strong>
          Something was changed after it was cut. Run <code>make film FILM={film.slug}</code> to cut it again.
        </div>
      )}
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

// ---------- what the director has asked for ----------

const DIRECTED: Record<string, string> = {
  picture: "Picture", line: "Line", motion: "Motion", score: "Score brief", look: "Look", world: "Who and where",
};

function DirectionLog({ film }: { film: FilmState }) {
  if (film.direction.length === 0) return null;
  return (
    <details className="calls">
      <summary>{plural(film.direction.length, "note")} you have given on this film</summary>
      <ol className="notes">
        {film.direction.map((entry, n) => (
          <li key={`${entry.ts}-${n}`}>
            <b>
              {DIRECTED[entry.target] ?? entry.target}
              {entry.shot ? `, ${entry.shot}` : ""}
            </b>
            <span className="quiet"> {new Date(entry.ts).toLocaleString()}</span>
            <p>&ldquo;{entry.note}&rdquo;</p>
            <p className="quiet">{entry.what_changed}</p>
          </li>
        ))}
      </ol>
    </details>
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
