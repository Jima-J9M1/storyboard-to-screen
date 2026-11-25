# Costs

Generated from `runs.jsonl` by `python -m core.costs` on 2026-11-25. Do not edit by hand: run `make costs` again.

The log holds 139 attempts at outside calls, 72 of which succeeded.

## What was paid

Nothing. Every call used a free tier, and the log's `cost_usd` adds up to $0.00.

## Time per stage

Latency is the wall-clock time of each call, measured by the pipeline. "Time lost" is the time spent on attempts that failed.

| Stage | Attempts | Succeeded | Failed | Time in successful calls (min) | Median successful call (s) | Time lost to failures (min) |
| --- | --- | --- | --- | --- | --- | --- |
| Research | 24 | 6 | 18 | 1.2 | 1.8 | 3.3 |
| Script (three agents) | 21 | 3 | 18 | 1.9 | 19.1 | 4.2 |
| Voice | 61 | 34 | 27 | 2.5 | 4.2 | 0.9 |
| Pictures | 16 | 15 | 1 | 2.7 | 10.5 | 0.6 |
| Music | 3 | 1 | 2 | 0.2 | 12.8 | 53.5 |
| Experiments (E2, E4) | 14 | 13 | 1 | 1.1 | 3.7 | 0.0 |

Radio cut, Moving shots and Edit call no outside service. They run in FFmpeg on the director's machine and are not in the log.

## GPU minutes

| Stage | Model | GPU | GPU session (min) | Per candidate (s) |
| --- | --- | --- | --- | --- |
| Music | ace-step-1.5-turbo (Kaggle T4) | Tesla T4, 15360 MiB | 2.9 | 11.3, 8.0, 8.1 |

Total: 2.9 GPU minutes, all on Kaggle's free allowance.

## Each service

| Service | Used for | Succeeded | Failed | Median time (s) | Tokens in | Tokens out |
| --- | --- | --- | --- | --- | --- | --- |
| `@cf/black-forest-labs/flux-2-klein-4b` | Experiments (E2, E4), Pictures | 19 | 1 | 9.1 |  |  |
| `ace-step-1.5-turbo (Kaggle T4)` | Music | 1 | 2 | 12.8 |  |  |
| `gemini-3.1-flash-tts-preview` | Voice | 2 | 6 | 6.5 | 60 | 448 |
| `gemini-3.5-flash` | Experiments (E2, E4), Research, Script (three agents), Voice | 20 | 0 | 3.9 | 7834 | 3967 |
| `gemini-3.7-flash` | Research, Script (three agents) | 0 | 15 | never answered |  |  |
| `gemini-3.8-flash` | Research, Script (three agents) | 0 | 21 | never answered |  |  |
| `gemini-3.8-flash-lite-tts` | Experiments (E2, E4), Voice | 11 | 9 | 3.7 | 149 | 1272 |
| `gemini-3.8-flash-tts` | Voice | 13 | 13 | 5.4 | 425 | 3498 |
| `macos-say` | Voice | 2 | 0 | 1.4 |  |  |
| `web-page` | Research | 2 | 0 | 0.8 |  |  |
| `wikidata-entity` | Research | 1 | 0 | 2.1 |  |  |
| `wikipedia-api` | Research | 1 | 0 | 1.5 |  |  |

## Why calls failed

| Reason | Attempts |
| --- | --- |
| quota or rate limit (HTTP 429) | 34 |
| model overloaded (HTTP 503) | 20 |
| other | 9 |
| timed out | 4 |

## Free-tier limits met

These are what the log shows, not what the providers publish. The published limits still need to be read and added here.

- Gemini text (`gemini-3.8-flash`, `gemini-3.7-flash`): refused with "quota exceeded" or "high demand" on every attempt so far; `gemini-3.5-flash` answered every time it was reached.
- Gemini voice: a few calls a minute. A burst of ten lines was refused nine times; waiting 20 to 40 seconds cleared it.
- Lyria music models: refused with "quota exceeded" on the first call, so they are not available on the free tier.
- Cloudflare Workers AI: 19 pictures made without a refusal.

## List-price equivalent

Not yet worked out. The token counts and call counts above are what a price would be multiplied by; the providers' current price lists have not been read into this repo, and no price is stated here from memory.
