# Architecture

This project is a machine that makes a 60–90 second narrated short film from a title.
This document explains how it is built and why. Each decision is given as the problem it answers.

Status on 25 November 2026: every stage is built. Each table below says what exists and what is planned.

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

## Many films, one machine

The system is not built around one story. Each film is a folder under `films/`, named from its title:

```
films/gebisa-ejeta/
  brief.json        the director's input
  storyboard.json   the approved plan
  research/         sources and facts
  outputs/          images, audio, video
  cache/            what was built from which inputs
```

Every command takes the film's name: `make research FILM=lalibela`. The default is `gebisa-ejeta`, the film submitted for the assignment, so `make film` with no name rebuilds that one.

Films share the code, the schemas and one run log, `runs.jsonl`, in which every line names its film. They share nothing else, so work on one film cannot disturb another's cache or outputs. A film's name is checked against a strict pattern before it is used as a path, so it cannot point outside `films/`.

Keeping the halves apart is what lets an agent write the story without making the film unrepeatable: an agent may answer differently each time it is asked, but it is asked once, and its approved answer is saved.

## Contracts

A contract is a file whose shape is fixed by a JSON Schema in `schema/`. Stages do not call each other. Each one reads the contracts and the files earlier stages left on disk.

| File | Written by | Read by | Holds |
|---|---|---|---|
| `films/<name>/brief.json` | the director | every agent | title, audience, the feeling to leave them with, narration languages, optional extra source pages |
| `films/<name>/research/` | the Researcher | the other agents | one record per source; the subject and its likeness policy; `facts.json`, the numbered facts with the source and quote behind each |
| `films/<name>/storyboard.json` | the agents, then the director | every stage | per shot: duration, shot size, image prompt, motion prompt, narration per language, English subtitle, reason, source fact ids, seed. Per film: style block, reference sheet, music, end card |

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
| Researcher | source records, subject, likeness policy | none (Wikipedia, Wikidata and the pages listed in the brief) | Built |
| Researcher, step 2 | the source as numbered facts, each quoting the source | Gemini | Built |
| Screenwriter | narration, subtitles, fact ids | Gemini | Built |
| Storyboard artist | style block, reference sheet, each shot's size, picture, movement and reason | Gemini | Built |
| Composer | music caption, tempo, key, cues | Gemini | Built |
| Translator | narration in every language other than English | Gemini | Built |

**Checks on every draft.** Code checks each agent's reply before it is saved: 8 to 12 shots, 130 to 190 words, a running time of 60 to 90 seconds worked out from the word count, every cited fact exists, no quotation marks, each shot size used at least twice, and no picture prompt names a subject who may not be shown. A reply that fails is retried.

**Who and where.** The storyboard carries a `world_block`: conditional rules for how the story's people, homes, land and crops look when they appear ("Any person is ...", "Any village home is ..."). The Storyboard artist writes it from the researched facts and the picture stage adds it to every prompt. Without it the picture model drew people and places from its own defaults; written as a plain description it put villagers into every shot (EXPERIMENTS.md, E6).

**Directing with a note.** Editing a JSON file is a poor way to direct. The director can instead say what is wrong with one thing a stage made ("there are three hands, show only two"). The Reviser agent rewrites the one storyboard field that produced it, under the same checks as the first draft, and the stage remakes that one item; the cache leaves everything else alone. Every note is appended to the film's `direction.jsonl` with the text before and after, so the film's history shows what a person decided. The film's rules outrank a note: a note cannot get a protected person named in a picture.

**The director owns the storyboard.** The agents write `storyboard.json` only when the film has none. After that a new draft goes to `storyboard.draft.json`, so re-running the agents can never undo the director's edits.

**A story the director tells.** A film does not have to be about something on Wikipedia. If the brief holds a `story` in the director's own words, that telling is recorded as the source and the facts are drawn from it under the same quote check; no public source is consulted. Because the system cannot look up who in such a story is a real person, it is treated as being about real people: nobody in it is shown with a recognisable face, voiced or quoted until the director records consent.

**The quote check.** A language model can state things its source does not say. So the Researcher must return, with every fact, the exact words from the source that support it, and code checks that those words are in the text of the source the fact names. A reply with a quote that is not there word for word is rejected and retried. Later agents may only narrate facts from this list.

**Source text and copyright.** Wikipedia's text is openly licensed, so it is committed. Other pages belong to their publishers, so only a record is committed: the address, the date, the word count and a fingerprint of the text. The text itself stays in a git-ignored folder and is fetched again if it is needed. The facts cache is keyed on the fingerprints, so a clean clone can tell the facts are current without fetching anything.

**The likeness guard.** The Researcher asks Wikidata what the title is. If it is a living person, it records the policy `no_likeness`: the film may not show them, voice them or give them invented quotes unless `ETHICS.md` holds a consent record. The policy is decided by code from a public record, not left to a prompt.

## The film half: stages

| Stage | Reads | Writes | Runs on | Status |
|---|---|---|---|---|
| validate | `brief.json`, `storyboard.json` | nothing | local | Built |
| keyframes | style block, reference sheet, image prompts, seeds, `use_reference` | the reference sheet, one picture per shot, and a contact sheet for review | FLUX.2 klein 4B on Cloudflare Workers AI | Built |
| video | pictures, motion prompts and seeds of the shots marked `video` | one generated clip per shot and shape, and the GPU job's report | Wan 2.2 TI2V-5B on a Kaggle GPU | Built |
| moving shots | generated clips where they exist, otherwise pictures and motion prompts; shot lengths | one clip per shot in each shape (9:16 and 16:9), fitted to the shot's length | local FFmpeg | Built |
| music | music caption, tempo, key, one seed per candidate | score candidates, and the GPU job's own report | ACE-Step 1.5 turbo on a Kaggle GPU | Built |
| narration | narration lines, voice and style | one audio file per shot per language, and the measured timings | Gemini TTS; the Mac's built-in voice if every model fails | Built |
| radio cut | the narration files | narration over placeholder music on a black screen | local FFmpeg | Built |
| assembly | clips, narration, the chosen score, subtitles, end card | the film in 9:16 and 16:9, and `report.json` with its measured length and loudness | local FFmpeg and Pillow | Built |

## Caching

**Problem.** Generation is slow and the quota is small, so nothing should be made twice.

**Decision.** Before a stage makes anything, it computes a hash of that item's inputs: a short fingerprint that changes if any input changes. Each stage keeps a manifest in the film's `cache/<stage>.json` that records, per item, the hash that produced it and the files it wrote.

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
| The video model has not made a shot's clip (it failed, or the job's time ran out) | The Moving shots stage gives that shot a camera move over its picture and lists it as a fallback in `moves.json`. The film can always be cut. | Built |
| The GPU runs out of memory on a clip | The job retries with fewer frames (81, then 49, then 33). | Built |
| The video model returns a blank clip | The job reloads the model at a different numeric precision and retries. | Built |
| No score has been chosen | The Edit stage uses a quiet placeholder chord and marks the film as a rough cut in `report.json`. | Built |
| The Kaggle GPU job fails | The job writes its own report, with each step's output and the traceback. The stage saves it as `job_report_failed.json` and stops. | Built |
| The title has no Wikipedia article | The Researcher stops and says to change the title. | Built |
| A model refuses with "quota exceeded" | It is not retried, because the quota will not clear in seconds. The next model is tried at once. | Built |
| A narration file says more or less than its line | Every file is transcribed by a model and compared with its line; a mismatch is reported. | Built |
| A line is longer than its shot | The voice stage reports each one with both lengths. The radio cut lets the next line wait, and says how far over the plan it ran. | Built |
| A source page is blocked, empty or a stub | It counts as a failed fetch: retried, logged, and never saved as a source. | Built |

Every outside call goes through one function, `core.runlog.logged_call`, so no stage can skip the retry or the log. The first real case is in `FAILURES.md`, entry F1.

## The run log

`runs.jsonl` gets one line per attempt at an outside call.

| Field | Meaning |
|---|---|
| `ts` | when, in UTC |
| `film` | which film the call was for |
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
| `films/` | one folder per film |
| `frontend/` | the production board, a Next.js app (`make board`) |
| `schema/` | the JSON Schemas |
| `tests/` | unit tests; they need no network and no keys |

`core/` depends on neither half. The halves do not import each other; they meet only at `storyboard.json`.

## The production board

`make board` starts a Next.js app at `http://127.0.0.1:3000`.

| Page | Shows |
|---|---|
| `/` | every film with a strip of its nine stages, a form to start a new film, and the repo's paperwork: required documents, experiments, failures |
| `/films/<name>` | one film, laid out like a film's page on a film site: its picture behind its title, running time and language, a button that plays it full screen, and credits naming the model behind each part. Below that, a sidebar lists the finished film and the nine stages in order, from Intent to Edit, and the main area shows whichever is chosen. "The film" view has the player, a timeline of shots that jumps the player to any shot, the measured release checklist and the credits. Each stage's view shows its brief, the stage it is at and what blocks it; the finished films, radio cut and score candidates, playable in the page; the storyboard with each shot's picture and narration audio; the sources and facts; its part of the run log |

**Problem.** A second program that reads the repo would need its own idea of what "done" and "valid" mean, and the two would drift apart.

**Decision.** The board does not read the repo's files. Its server asks the pipeline, by running `python -m core.status`, and draws the JSON that comes back. `core/status.py` is the one place that decides a stage's status, and it uses the same validation as the stages. The page asks again every five seconds.

The board also serves the generated files themselves, so they can be looked at and played. It serves only what the status report lists, only pictures, sound and video, and only from inside a film's `outputs/` folder; a request for anything else gets "not found".

The board changes the repo in two ways, both by running pipeline code and never by writing files itself. It can start a new film (`python -m core.films new`), and it can pass the director's note on one item to the Reviser (`python -m agents.reviser`), which is the one place the board causes a model to be called. It can also start a stage (`python -m core.run_stage`), which is where the list of stages that may be started from a browser is kept; the hours-long GPU stages are not on it. It cannot edit a storyboard directly. It listens on this machine only, runs commands without a shell, and refuses a request to start a film that comes from another website. The pipeline does not need it.

## Text on screen

Generated pictures never contain words. Subtitles and the end card are drawn in code with Pillow, using its built-in font, and laid over the picture by FFmpeg. That keeps the result the same on every machine: no font has to be installed, and FFmpeg does not need to be built with text support (the copy on the development machine was not).

A subtitle card has at most two lines. A line's cards share its spoken time in proportion to their length.

## What is committed

| Kind of file | Committed? | Why |
|---|---|---|
| Pictures, narration audio, score candidates | Yes | They cost model calls. With them and the cache manifests in the repo, a clean clone needs no keys. |
| The finished films and the radio cut | Yes | So the result can be inspected without running anything. |
| Per-shot clips and working files | No | FFmpeg rebuilds them from the pictures in a few minutes. |
| Text of copyrighted source pages | No | It belongs to its publishers. A record of each page is committed. |

## Generated video on a small GPU

The video model's documentation asks for a 24 GB GPU at 720p. Kaggle's free GPU has 15 GB. The job therefore:

- works at 480p (480 x 832 tall, 832 x 480 wide) with 81 frames, about 3.4 seconds;
- keeps one part of the model on the GPU at a time, and decodes the video in tiles;
- makes clips in storyboard order, tall first, saving each as it finishes, and stops starting new ones when its time budget is nearly spent.

A generated clip is 3.4 seconds and a shot is 7 to 10. So each shot gets a second clip that starts from the last frame of the first and carries the motion on; the Moving shots stage joins the two and stretches them to the shot's exact length (1.2 to 1.6 times), with in-between frames computed by FFmpeg and a slow push-in. A clip is never held on a frozen frame. A shot can refuse its continuation with `"extend": false`, for when the continuation shows something the film must not.

Each clip runs 0.4 seconds past its shot, and the Edit stage dissolves from one shot into the next over those frames, so the narration's timing does not move.

The pictures reach Kaggle as a private dataset, and the clips come back as the job's output. `core/kaggle.py` holds the upload, wait and download steps; a job that has already run can be collected without sending a new one.

## Open decisions

- **Checking narration in languages other than English.** The transcript check cannot tell a mispronounced line from a mis-transcribed one in Amharic (EXPERIMENTS.md, E8). A second transcriber, or a human sign-off recorded in the storyboard, is needed.
- **The music stage has its own copy of the Kaggle steps.** It was written first; it should be moved onto `core/kaggle.py`.
