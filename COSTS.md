# Costs

Generated from `runs.jsonl` by `python -m core.costs` on 2026-11-25. Do not edit by hand: run `make costs` again.

The log holds 373 attempts at outside calls, 167 of which succeeded.

## What was paid

Nothing. Every call used a free tier, and the log's `cost_usd` adds up to $0.04.

## Time per stage

Latency is the wall-clock time of each call, measured by the pipeline. "Time lost" is the time spent on attempts that failed.

| Stage | Attempts | Succeeded | Failed | Time in successful calls (min) | Median successful call (s) | Time lost to failures (min) |
| --- | --- | --- | --- | --- | --- | --- |
| Research | 33 | 9 | 24 | 1.6 | 2.1 | 4.1 |
| Script (three agents) | 45 | 7 | 38 | 2.9 | 17.7 | 10.8 |
| Voice | 209 | 70 | 139 | 4.8 | 3.7 | 4.6 |
| Pictures | 67 | 65 | 2 | 10.6 | 8.3 | 0.6 |
| Music | 4 | 2 | 2 | 6.3 | 188.0 | 53.5 |
| Experiments (E2, E4) | 14 | 13 | 1 | 1.1 | 3.7 | 0.0 |
| video | 1 | 1 | 0 | 9.2 | 553.3 | 0.0 |

Radio cut, Moving shots and Edit call no outside service. They run in FFmpeg on the director's machine and are not in the log.

## GPU minutes

| Stage | Model | GPU | GPU session (min) | Per candidate (s) |
| --- | --- | --- | --- | --- |
| Music | ace-step-1.5-turbo (Kaggle T4) | Tesla T4, 15360 MiB | 2.9 | 11.3, 8.0, 8.1 |
| video | wan-2.2-ti2v-5b (Kaggle T4) | Tesla T4, 15360 MiB | 6.1 |  |
| Music | ace-step-1.5-turbo (Kaggle T4) | Tesla T4, 15360 MiB | 5.1 | 11.3, 7.9, 7.9 |

Total: 14.1 GPU minutes, all on Kaggle's free allowance.

## Each service

| Service | Used for | Succeeded | Failed | Median time (s) | Tokens in | Tokens out |
| --- | --- | --- | --- | --- | --- | --- |
| `@cf/black-forest-labs/flux-2-klein-4b` | Experiments (E2, E4), Pictures | 69 | 2 | 8.3 |  |  |
| `ace-step-1.5-turbo (Kaggle T4)` | Music | 2 | 2 | 188.0 |  |  |
| `addis-voices-2:am-yohanes-calm` | Voice | 10 | 30 | 3.0 |  |  |
| `gemini-3.1-flash-tts-preview` | Voice | 7 | 16 | 6.8 | 335 | 1636 |
| `gemini-3.5-flash` | Experiments (E2, E4), Research, Script (three agents), Voice | 30 | 13 | 4.9 | 17119 | 8230 |
| `gemini-3.5-flash-lite` | Voice | 13 | 2 | 2.3 |  |  |
| `gemini-3.7-flash` | Research, Script (three agents) | 0 | 28 | never answered |  |  |
| `gemini-3.8-flash` | Research, Script (three agents) | 0 | 34 | never answered |  |  |
| `gemini-3.8-flash-lite-tts` | Experiments (E2, E4), Voice | 13 | 35 | 3.6 | 229 | 1599 |
| `gemini-3.8-flash-tts` | Voice | 14 | 44 | 5.0 | 481 | 3704 |
| `macos-say` | Voice | 2 | 0 | 1.4 |  |  |
| `wan-2.2-ti2v-5b (Kaggle T4)` | video | 1 | 0 | 553.3 |  |  |
| `web-page` | Research | 2 | 0 | 0.8 |  |  |
| `wikidata-entity` | Research | 2 | 0 | 2.7 |  |  |
| `wikipedia-api` | Research | 2 | 0 | 1.1 |  |  |

## Why calls failed

| Reason | Attempts |
| --- | --- |
| quota or rate limit (HTTP 429) | 117 |
| model overloaded (HTTP 503) | 44 |
| other | 40 |
| timed out | 5 |

## Free-tier limits met

These are what the log shows, not what the providers publish. The published limits still need to be read and added here.

- Gemini text (`gemini-3.8-flash`, `gemini-3.7-flash`): refused with "quota exceeded" or "high demand" on every attempt so far; `gemini-3.5-flash` answered every time it was reached.
- Gemini voice: a few calls a minute. A burst of ten lines was refused nine times; waiting 20 to 40 seconds cleared it.
- Lyria music models: refused with "quota exceeded" on the first call, so they are not available on the free tier.
- Cloudflare Workers AI: 69 pictures made without a refusal.

## List-price equivalent

Not yet worked out. The token counts and call counts above are what a price would be multiplied by; the providers' current price lists have not been read into this repo, and no price is stated here from memory.
