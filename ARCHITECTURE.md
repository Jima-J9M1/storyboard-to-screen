# Architecture

This project is a machine that makes a 60–90 second narrated short film from a title.
This document explains how it is built and why. Each decision is given as the problem it answers.

Status on 24 November 2026: the foundation and the Researcher agent are built. Each table below says what exists and what is planned.

## The problem

A stranger must be able to clone this repo, run one command, and get the film. Four things make that hard.

| Difficulty | Consequence |
|---|---|
| The models are slow | One 5-second video clip takes several minutes of GPU time. |
| The models fail | Free quotas run out, jobs time out, results come back wrong. |
| The film changes | Two rounds of audience testing must change the film. |
| Everything must be provable in writing | The run has to leave a record that can be read without watching the film. |

## The options we considered

| Option | One command? | Survives a failure? | Cheap to change one shot? | Chosen |
|---|---|---|---|---|
| Make the film by hand in web tools and a video editor | No | — | — | No |
| One long script that does everything | Yes | No: a late failure loses all earlier work | No: any change re-runs everything | No |
| A written plan, plus small separate stages that each read it | Yes | Yes: each stage keeps its own output | Yes: only the changed shot is redone | **Yes** |

## The shape

```
brief.json ──> agents ──> storyboard.json ──> stages ──> film
(a person      (draft     (a person           (render
 writes it)     the plan)  approves it)        the plan)
```

There are two halves, and one file sits between them.

- **The story half** (`agents/`) turns a title into a plan. It uses language models, so its output is a draft that a person edits and approves.
- **The film half** (`pipeline/`) turns the approved plan into the film. It makes no creative decisions; it renders what the plan says.
- **The plan** is `storyboard.json`. Because the approved plan is committed, the film half gives the same film on any machine.

Keeping the halves apart is what lets an agent write the story without making the film unrepeatable: an agent may answer differently each time it is asked, but it is asked once, and its approved answer is saved.

## Contracts

A contract is a file whose shape is fixed by a JSON Schema in `schema/`. Stages do not call each other. Each one reads the contracts and the files earlier stages left on disk.

| File | Written by | Read by | Holds |
|---|---|---|---|
| `brief.json` | the director | every agent | title, audience, the feeling to leave them with, narration languages |
| `research/<slug>/` | the Researcher | the other agents | source text with its revision and licence; the subject and its likeness policy |
| `storyboard.json` | the agents, then the director | every stage | per shot: duration, shot size, image prompt, motion prompt, narration per language, English subtitle, reason, source fact ids, seed. Per film: style block, reference sheet, music, end card |

**Validation happens before every run.** `core/contracts.py` loads each file through its schema and refuses to continue if it fails. The schema carries the structural rules. Rules a schema cannot express are checked in code.

| Rule | Where it is enforced |
|---|---|
| 8 to 12 shots | schema |
| Every shot has a reason | schema |
| The end card says the film was made with AI | schema |
| No unknown fields (catches typing mistakes in field names) | schema |
| The film runs 60–90 s including the end card | code |
| Every narration language has a line on every shot | code |
| A narrated shot has an English subtitle | code |
| Audience and feeling are written before anything is generated | code |

A broken plan is rejected in under a second, before any GPU time is spent on it.

## The story half: agents

Each agent owns named fields of the storyboard and writes nothing else. `agents/README.md` holds the ownership table.

| Agent | Produces | Model | Status |
|---|---|---|---|
| Researcher | source text, subject, likeness policy | none (Wikipedia and Wikidata fetches) | Built |
| Researcher, step 2 | the source as numbered facts, each quoting the source | Gemini | Built |
| Screenwriter | narration, subtitles, fact ids | Gemini | Planned |
| Storyboard artist | shots, sizes, prompts, reasons | Gemini | Planned |
| Art director | style block, reference sheet | Gemini | Planned |
| Composer | music caption, tempo, key, cues | Gemini | Planned |
| Translator | narration in the extra languages | Gemini | Planned |

**The quote check.** A language model can state things its source does not say. So the Researcher must return, with every fact, the exact words from the source that support it, and code checks that those words are in the source text. A reply with a quote that is not there word for word is rejected and retried. Later agents may only narrate facts from this list.

**The likeness guard.** The Researcher asks Wikidata what the title is. If it is a living person, it records the policy `no_likeness`: the film may not show them, voice them or give them invented quotes unless `ETHICS.md` holds a consent record. The policy is decided by code from a public record, not left to a prompt.

## The film half: stages

| Stage | Reads | Writes | Runs on | Status |
|---|---|---|---|---|
| validate | `brief.json`, `storyboard.json` | nothing | local | Built |
| keyframes | style block, reference sheet, image prompts, seeds | one image per shot | Cloudflare Workers AI | Planned |
| moving shots | keyframes, motion prompts | one clip per shot | Kaggle GPU; Ken Burns locally as the fallback | Planned |
| music | music caption, tempo, key, seeds | score candidates | Kaggle GPU | Planned |
| narration | narration lines | one audio file per shot per language | Gemini TTS | Planned |
| assembly | all of the above | the film in 9:16 and 16:9 | local FFmpeg | Planned |

## Caching

**Problem.** Generation is slow and the quota is small, so nothing should be made twice.

**Decision.** Before a stage makes anything, it computes a hash of that item's inputs: a short fingerprint that changes if any input changes. Each stage keeps a manifest in `cache/<stage>.json` that records, per item, the hash that produced it and the files it wrote.

An item is skipped when its recorded hash matches and its files still exist. Otherwise it is regenerated.

What follows from that:
- Changing one shot's prompt changes one hash, so one shot is regenerated and the rest are skipped.
- Running again with no changes makes no outside calls at all.
- The manifests and outputs are committed, so a clean clone skips work that is already in the repo.

`core/cache.py` implements this. The Researcher uses it today: a second `make research` makes no fetch.

## Failure handling

| What goes wrong | What the system does | Status |
|---|---|---|
| The plan is malformed | Validation rejects it before any stage runs, listing every problem. | Built |
| An outside call fails | It is retried up to three times with a doubling wait. Every attempt is logged. | Built |
| A model fails three times | The next model in the list is tried (`core/llm.py`). The model that answered is saved with the output. | Built |
| A model's reply breaks the schema or a check | It counts as a failed attempt: logged, retried, never saved. | Built |
| Every model fails | The stage stops with a clear error. Finished items stay cached, so the next run resumes where it stopped. | Built |
| Video generation fails or the GPU quota runs out | The shot falls back to a Ken Burns pan and zoom over its keyframe. | Planned |
| The title has no Wikipedia article | The Researcher stops and says to change the title. | Built |

Every outside call goes through one function, `core.runlog.logged_call`, so no stage can skip the retry or the log. The first real case is in `FAILURES.md`, entry F1.

## The run log

`runs.jsonl` gets one line per attempt at an outside call.

| Field | Meaning |
|---|---|
| `ts` | when, in UTC |
| `stage`, `item` | which stage, and which unit of it (for example a shot id) |
| `kind` | `model` for a generative model call, `fetch` for a plain data fetch |
| `model`, `params`, `seed` | exactly what was asked |
| `input_hash` | links the line to its cache entry |
| `attempt`, `status`, `error` | the retry number and how it ended |
| `latency_s`, `cost_usd` | measured time and list-price cost |
| `tokens_in`, `tokens_out` | for text model calls, the token counts the API reported |

The cost and latency tables in `COSTS.md` will be generated from this file by a script.

## Folder map

| Folder | Holds |
|---|---|
| `agents/` | the story half, one module per agent |
| `pipeline/` | the film half, one script per stage |
| `core/` | shared plumbing: paths, contracts, run log, cache, HTTP |
| `schema/` | the JSON Schemas |
| `tests/` | unit tests; they need no network and no keys |
| `research/`, `cache/`, `outputs/` | what runs produce |

`core/` depends on neither half. The halves do not import each other; they meet only at `storyboard.json`.

## Open decisions

- **How the local command starts a Kaggle GPU job.** The options are the Kaggle API, which pushes a notebook and polls for its output, or a manual run whose outputs are downloaded. Not yet decided.
- **What a clean clone regenerates.** Reusing committed outputs makes the one command work without GPU access. A flag to force full regeneration is planned.
