# Failures

What broke, what we tried, and what fixed it. Every entry points to the log lines that show it.

## F1. Gemini 3.8 Flash answered "503 high demand" for the whole run

**When:** 24 November 2026, 18:04–18:08 UTC, first run of the Researcher's fact step.

**Symptom.** `make research` stopped with `gemini-3.8-flash failed after 3 attempts`. The API replied
`HTTP 503 ... "This model is currently experiencing high demand"`. One attempt hung until the 120-second read timeout.

**What we tried.**
1. Ran the command again a few seconds later. The same three attempts failed the same way, so waiting 2, 4 and 8 seconds between attempts was not enough to outlast the spike.
2. Added a list of models to `core/llm.py`, tried in order, each with three attempts: `gemini-3.8-flash`, then `gemini-3.7-flash`, then `gemini-3.5-flash`.

**Result.** On the next run 3.8 Flash failed three times, 3.7 Flash failed three times with the same 503, and 3.5 Flash answered on its first attempt in 23.2 seconds. The 13 facts it returned all passed the quote check.

**What fixed it.** The model fallback. The model that actually answered is saved in `films/gebisa-ejeta/research/facts.json`, so the record shows which model wrote the facts.

**Evidence.** `runs.jsonl`, stage `research`, item `facts`: twelve `error` lines followed by one `ok` line for `gemini-3.5-flash`.

**What it taught us.** The newest free model is the busiest one. A retry on the same model does not help during a demand spike; a different model does.

## F2. The World Food Prize site returned an empty page to the pipeline

**When:** 24 November 2026, while choosing a second source.

**Symptom.** Fetching the laureate page at `worldfoodprize.org` returned `HTTP 202` with zero bytes of content. A search engine lists the same address as a normal page, so the site appears to answer scripts differently from browsers; we did not confirm this in a browser.

**What we tried.**
1. Fetched the page with the pipeline's own user agent. Result: 202, empty.
2. Looked for another publisher with the same material. Two Purdue University news pages about the same prize returned `200` with about 800 and 950 words of prose.

**What fixed it.** We used the Purdue pages as the extra sources. We did not disguise the pipeline as a browser to get past the block: a site that refuses scripts has said no.

**What changed in the code.** `core/http.py` now treats any status other than 200, or an empty body, as a failure, so a blocked page is retried and logged, not saved as an empty source. The Researcher also refuses a page with fewer than 150 words of prose.

**Evidence.** This fetch was made by hand before the feature existed, so it has no `runs.jsonl` line. The guards are in `core/http.py` (`_read`) and `agents/researcher.py` (`fetch_page`).

## F3. The two newest Gemini models refused the story drafts with "quota exceeded"

**When:** 25 November 2026, first run of `make story`.

**Symptom.** `gemini-3.8-flash` and `gemini-3.7-flash` answered `HTTP 429 ... "You exceeded your current quota"` for the Screenwriter, the Storyboard artist and the Composer. Some attempts returned 503 or hung until the read timeout instead.

**What we tried.** Nothing new was needed. The model fallback added for F1 moved each agent on to `gemini-3.5-flash` after three failed attempts per model.

**Result.** All three agents were drafted by `gemini-3.5-flash`, and each reply passed its checks. The run made 21 attempts for 3 successful calls.

**What it cost.** Time: each failed model takes three attempts with waits of 2 and 4 seconds, and a hung attempt takes 120 seconds.

**Not yet fixed.** A 429 for quota will not succeed on a retry seconds later, so retrying it three times is wasted. The fallback should skip straight to the next model on a quota error. The free-tier limits for each model also still need to be looked up and written into `COSTS.md`.

**Evidence.** `runs.jsonl`, stage `story`.

## F4. The narrator read its own stage direction aloud

**When:** 25 November 2026, first run of the voice stage.

**Symptom.** Ten lines took 121.8 seconds to speak, where the plan allowed about 70. Every line overran its shot by three to five seconds. The files had almost no silence at either end, so it looked like very slow speech: 1.3 words a second.

**What we tried.**
1. Measured the silence in each file. Lead and tail were under half a second, so padding was not the cause.
2. Spoke one line four ways with only the style changed (EXPERIMENTS.md, E2). With no style the line took 6.9 s; with the style written as "Say in a ... voice:" it took 12.6 s.
3. Had a model transcribe the long file. It began with the instruction itself: the voice was reading the direction aloud before each line.
4. Tried the style as a system instruction: refused with HTTP 400. Tried it in square brackets: not spoken.

**What fixed it.** The style is sent as `[calm, warm, unhurried] line`. After re-recording, the ten lines take 80.8 seconds and every transcript matches its line.

**What changed in the code.** No agent can listen, so the fault was invisible until a transcript was made. The voice stage now transcribes every file and reports any that says more or fewer words than its line (`pipeline/narration.py`, `heard_problem`).

**Evidence.** `runs.jsonl`, stages `narration` and `experiment`. `films/gebisa-ejeta/outputs/narration/timings.json` holds what was heard for each line.

## F5. Two lines of the narration were spoken by a different voice

**When:** 25 November 2026, second run of the voice stage.

**Symptom.** Nothing looked wrong: ten files, every transcript matched. The timings file showed that shots s04 and s09 had been spoken by `macos-say`, the Mac's built-in voice, and the other eight by Gemini. The film had two narrators.

**Cause.** The free tier allows only a few voice calls a minute. Nine calls were refused with HTTP 429. The stage treated 429 as "do not retry", moved through the model list, and ended at the local fallback voice. A third model, `gemini-3.1-flash-tts-preview`, failed for a different reason: it returns raw audio whose type is written in lower case, which the converter did not recognise.

**What we tried and what fixed it.**
1. A refused voice call now waits 20 and then 40 seconds and tries again, which is long enough for a per-minute limit to clear.
2. The local voice is no longer a silent fallback. It is used only when the stage is run with `--rough`, and those lines are re-recorded the next time it runs without it.
3. If no model can speak a line, the stage says which lines are missing and exits with an error; finished lines stay cached.
4. The audio converter now recognises the type in either case.

**Result.** The two lines were re-recorded. All ten are now spoken by Gemini models with the same voice name.

**Still open.** The ten lines came from three different Gemini models. They share a voice name, but whether they sound the same has to be checked by ear. The stage prints a reminder when more than one model was used.

**Evidence.** `runs.jsonl`, stage `narration`. `films/gebisa-ejeta/outputs/narration/timings.json` records the model for each line.

## F6. The score job waited 48 minutes for a GPU, then failed in 9 seconds

**When:** 25 November 2026, first runs of the music stage.

**Symptom.** The job uploaded to Kaggle and sat at "queued". A first submission was still queued after 30 minutes and was abandoned. A second, which named the T4 GPU, finished after 48 minutes with an error.

**Cause.** Two separate things.
1. The queue. Kaggle's free GPUs were busy. Naming the GPU type did not obviously shorten the wait; one run each way is not enough to tell.
2. The failure itself: `Package 'ace-step' requires a different Python: 3.13.16 not in '<3.13,>=3.11'`. Kaggle's notebooks run Python 3.13, and ACE-Step 1.5 installs only on 3.11 or 3.12. The job's own report showed the job ran for 9.2 seconds in all: clone 1.5 s, install 7.6 s.

**What we tried and what fixed it.** The job no longer installs ACE-Step into Kaggle's Python. It installs `uv`, lets `uv sync` build ACE-Step's environment with a Python the project supports, and runs the generation inside it.

**What changed in the code.** A failed attempt costs most of an hour of queueing, so the job now tells us more each time: it records the Python and PyTorch versions, the real signatures of the library functions it calls, and the repository's file list if anything fails. It also retries once with the planner model loaded if generation refuses to run without it. The stage's time limit went from 45 to 150 minutes.

**Result.** The corrected job ran on its first attempt. On a Tesla T4 it took 176 seconds in all: 75 s to build the environment, 41.5 s to load the model, and 8 to 11 s to generate each 90-second candidate. The model's own Python was 3.12.3.

A third, smaller failure followed: the job had finished, but downloading its output timed out on the connection to Kaggle's file host. The stage now tries the download three times, and `--collect` fetches the result of a job that already ran without sending a new one.

**Evidence.** `runs.jsonl`, stage `music`: an `error` line with a latency of 2,898 seconds (the Python failure), an `error` line for the download, and the `ok` line. `films/gebisa-ejeta/outputs/music/job_report_failed.json` and `job_report.json` are the jobs' own records.
