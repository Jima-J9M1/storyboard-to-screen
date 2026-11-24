# Rules for any coding agent working in this repo

This repo is a system that turns a title into a 60–90 second narrated short film.
It is the submission for the 10 Academy "Heritage Short" assignment. The pipeline is what is graded.

## Before every task
1. Re-read the section of the assignment brief that covers the task. Do not work from memory of it.
2. Check the task against the hard rules below.
3. Before saying a task is done, check it against the rubric rows it affects and say which checks now pass.

If the brief and these rules disagree, the brief wins. Say so and fix this file.

## Shape of the system
Two halves, with `storyboard.json` between them.

| Half | Command | What it does |
|---|---|---|
| Story half | `make research`, `make story` | Reads `brief.json`, researches the title, drafts `storyboard.json`. A person edits and approves the result. |
| Film half | `make film` | Renders the approved storyboard: keyframes, moving shots, music, narration, assembly. |

- `brief.json` is the human input: title, audience, the feeling to leave them with, narration language.
- `storyboard.json` is the contract between every stage. Prompts, seeds and durations live there, never in code.
- A frontend comes last. It is a thin layer over the same commands; the pipeline must work without it.

## Where things go
| Folder | Holds | Rule |
|---|---|---|
| `agents/` | The story half: one module per agent. `agents/README.md` lists who owns which storyboard fields. | An agent writes only the fields it owns. |
| `pipeline/` | The film half: one script per stage. | No agent and no creative decision here; it renders what the storyboard says. |
| `core/` | Shared plumbing: paths, contracts, run log, cache, HTTP. | Both halves use it; it depends on neither. |
| `schema/` | JSON Schemas for `brief.json` and `storyboard.json`. | Change the schema and its tests together. |
| `tests/` | Unit tests. They use no network and no keys. | `make test` passes before any commit. |
| `research/`, `cache/`, `outputs/` | What runs produce. Committed, so a run can be inspected and a clean clone can skip finished work. | Never edited by hand. |
| `.claude/agents/` | Checker subagents used while building. | Never part of a run. |

## Hard rules
1. **One command.** `make film` must rebuild the film from a clean clone using only the README.
2. **Validate first.** Every stage validates `brief.json` and `storyboard.json` against `schema/` before doing anything.
3. **Log every model call** to `runs.jsonl`: model, parameters, seed, latency, cost. Use `core.runlog.logged_call`; never call a model around it.
4. **Cache by input hash.** A stage regenerates only what changed. A re-run with no changes makes zero model calls.
5. **Retry, then fall back.** Three attempts per call, then the documented fallback (for moving shots: Ken Burns over the keyframe).
6. **No secrets in git.** Keys live in `.env`. Only `.env.example` is committed.
7. **No real person's face, likeness or voice** without a consent record in `ETHICS.md`. For a living person the default is: never shown, never voiced, no invented quotes.
8. **Every narrated fact cites a source** recorded under `research/`.
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
