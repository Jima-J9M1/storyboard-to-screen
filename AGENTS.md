# Rules for any coding agent working in this repo

This repo is a system that turns a title into a 60–90 second narrated short film.
It holds many films, one folder each under `films/`. The film submitted for the 10 Academy "Heritage Short" assignment is `films/gebisa-ejeta`. The pipeline is what is graded.

## Before every task
1. Re-read the section of the assignment brief that covers the task. Do not work from memory of it.
2. Check the task against the hard rules below.
3. Before saying a task is done, check it against the rubric rows it affects and say which checks now pass.

If the brief and these rules disagree, the brief wins. Say so and fix this file.

## Shape of the system
Two halves, with a film's `storyboard.json` between them. Every command works on one film, chosen with `FILM=<name>`; the default is `gebisa-ejeta`.

| Half | Command | What it does |
|---|---|---|
| Start | `make new TITLE="..."` | Creates `films/<name>/brief.json` from a title. |
| Story half | `make research`, `make story` | Reads the brief, researches the title, drafts the storyboard. A person edits and approves the result. |
| Film half | `make film` | Renders the approved storyboard: keyframes, moving shots, music, narration, assembly. |

- `films/<name>/brief.json` is the human input: title, audience, the feeling to leave them with, narration languages, extra sources.
- `films/<name>/storyboard.json` is the contract between every stage. Prompts, seeds and durations live there, never in code.
- `runs.jsonl` is one log for the whole repo. Every line names its film.
- The frontend (`make board`) shows every film and where it is. The pipeline must work without it.

## Where things go
| Folder | Holds | Rule |
|---|---|---|
| `agents/` | The story half: one module per agent. `agents/README.md` lists who owns which storyboard fields. | An agent writes only the fields it owns. |
| `pipeline/` | The film half: one script per stage. | No agent and no creative decision here; it renders what the storyboard says. |
| `core/` | Shared plumbing: paths, contracts, run log, cache, HTTP, the text-model client, the status report. | Both halves use it; it depends on neither. |
| `films/<name>/` | One film: its brief, storyboard, `research/`, `outputs/` and `cache/`. | Films never read each other's folders. `research/`, `outputs/` and `cache/` are written by runs, never by hand. |
| `frontend/` | The production board, a Next.js app. | It gets every fact and every list of files from `python -m core.status`, and never decides a status itself. It serves the pictures, audio and video that list names, from a film's `outputs/` folder only. It changes the repo only through pipeline code, never by writing files itself: starting a new film (`core.films`), passing the director's note on one item to the Reviser (`agents.reviser`), and starting a stage (`core.run_stage`, which holds the list of stages that may be started this way). |
| `schema/` | JSON Schemas for `brief.json` and `storyboard.json`. | Change the schema and its tests together. |
| `tests/` | Unit tests. They use no network and no keys. | `make test` passes before any commit. |
| `.claude/agents/` | Checker subagents used while building. | Never part of a run. |

## Hard rules
1. **One command.** `make film` must rebuild the film from a clean clone using only the README.
2. **Validate first.** Every stage validates the film's `brief.json` and `storyboard.json` against `schema/` before doing anything.
3. **Log every model call** to `runs.jsonl`: model, parameters, seed, latency, cost. Use `core.runlog.logged_call`; never call a model around it.
4. **Cache by input hash.** A stage regenerates only what changed. A re-run with no changes makes zero model calls.
5. **Retry, then fall back.** Three attempts per call, then the documented fallback (for moving shots: Ken Burns over the keyframe).
6. **No secrets in git.** Keys live in `.env`. Only `.env.example` is committed.
7. **No real person's face, likeness or voice** without a consent record in `ETHICS.md`. For a living person the default is: never shown, never voiced, no invented quotes.
8. **Every narrated fact cites a source** recorded under the film's `research/`.
9. **No text inside generated images.** Titles, subtitles and the end card are added in code.
10. **Describe style by qualities.** Never name a living artist.
11. **Leave watermarks and provenance metadata intact** (SynthID, C2PA).
12. **Free stack only at run time**, as listed in the brief. The pipeline must not depend on a paid coding agent.

## Evidence rules
Graders read code, text and logs only. They open no media.
- Never invent a user test, an experiment result, a failure, a measurement or a quote.
- A step is not finished until its entry is written: `EXPERIMENTS.md` for a comparison, `FAILURES.md` for anything that broke.
- An experiment changes one thing, keeps the seed fixed, and points to its `runs.jsonl` lines.
- Numbers in `COSTS.md` are generated from `runs.jsonl`, not typed by hand.
- The public post is written by the director, not by an agent.

## Approval gates
Stop for the director's approval at each one, in this order:
story and intent → radio cut → keyframes → moving shots → edit.

## Working habits
- Small commits, one change each.
- Audience and intent go into `DESIGN.md` before the first generation call.
- Draft at low resolution, batch GPU jobs, finish only the chosen shots.
- Python, standard library where possible; dependencies go in `requirements.txt`.
- The frontend is Next.js with TypeScript. Pin exact versions of `next` and `react` in `frontend/package.json`.
