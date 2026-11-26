# Costs

Generated from `runs.jsonl` by `python -m core.costs` on 2026-11-26. Do not edit by hand: run `make costs` again.

The log holds 427 attempts at outside calls, 178 of which succeeded.

## What was paid

Nothing. Every call used a free tier, and the log's `cost_usd` adds up to $0.04.

## Time per stage

Latency is the wall-clock time of each call, measured by the pipeline. "Time lost" is the time spent on attempts that failed.

| Stage | Attempts | Succeeded | Failed | Time in successful calls (min) | Median successful call (s) | Time lost to failures (min) |
| --- | --- | --- | --- | --- | --- | --- |
| Research | 43 | 10 | 33 | 1.7 | 2.7 | 7.9 |
| Script (three agents) | 70 | 8 | 62 | 2.9 | 16.2 | 21.5 |
| Voice | 209 | 70 | 139 | 4.8 | 3.7 | 4.6 |
| Pictures | 69 | 67 | 2 | 10.8 | 8.2 | 0.6 |
| Music | 4 | 2 | 2 | 6.3 | 188.0 | 53.5 |
| Experiments (E2, E4) | 14 | 13 | 1 | 1.1 | 3.7 | 0.0 |
| direction | 12 | 2 | 10 | 0.1 | 2.1 | 0.2 |
| video | 6 | 6 | 0 | 410.2 | 3911.9 | 0.0 |

Radio cut, Moving shots and Edit call no outside service. They run in FFmpeg on the director's machine and are not in the log.

## GPU minutes

| Stage | Model | GPU | GPU session (min) | Per candidate (s) |
| --- | --- | --- | --- | --- |
| Music | ace-step-1.5-turbo (Kaggle T4) | Tesla T4, 15360 MiB | 2.9 | 11.3, 8.0, 8.1 |
| video | wan-2.2-ti2v-5b (Kaggle T4) | Tesla T4, 15360 MiB | 6.1 |  |
| Music | ace-step-1.5-turbo (Kaggle T4) | Tesla T4, 15360 MiB | 5.1 | 11.3, 7.9, 7.9 |
| video | wan-2.2-ti2v-5b (Kaggle T4) | Tesla T4, 15360 MiB | 144.9 | 754.8, 753.6, 753.9, 755.0, 754.1, 754.1, 753.4, 754.7, 754.3, 754.4, 753.7 |
| video | wan-2.2-ti2v-5b (Kaggle T4) | Tesla T4, 15360 MiB | 143.6 | 815.1, 823.6, 823.4, 823.7, 823.2, 823.9, 823.1, 823.6, 823.2, 824.4 |
| video | wan-2.2-ti2v-5b (Kaggle T4) | Tesla T4, 15360 MiB | 130.2 | 739.1, 742.7, 742.1, 742.2, 741.6, 742.8, 741.7, 741.8, 742.4, 742.3 |
| video | wan-2.2-ti2v-5b (Kaggle T4) | Tesla T4, 15360 MiB | 136.7 | 775.7, 780.6, 779.2, 779.0, 777.7, 779.3, 778.2, 779.7, 781.4, 780.5 |
| video | wan-2.2-ti2v-5b (Kaggle T4) | Tesla T4, 15360 MiB | 138.3 | 786.4, 790.0, 789.9, 789.9, 790.4, 790.7, 789.9, 792.4, 791.8, 791.7 |

Total: 707.8 GPU minutes, all on Kaggle's free allowance.

## Each service

| Service | Used for | Succeeded | Failed | Median time (s) | Tokens in | Tokens out |
| --- | --- | --- | --- | --- | --- | --- |
| `@cf/black-forest-labs/flux-2-klein-4b` | Experiments (E2, E4), Pictures | 71 | 2 | 8.2 |  |  |
| `ace-step-1.5-turbo (Kaggle T4)` | Music | 2 | 2 | 188.0 |  |  |
| `addis-voices-2:am-yohanes-calm` | Voice | 10 | 30 | 3.0 |  |  |
| `gemini-3.1-flash-lite` | Script (three agents) | 0 | 3 | never answered |  |  |
| `gemini-3.1-flash-tts-preview` | Voice | 7 | 16 | 6.8 | 335 | 1636 |
| `gemini-3.5-flash` | Experiments (E2, E4), Research, Script (three agents), Voice, direction | 30 | 25 | 4.9 | 17119 | 8230 |
| `gemini-3.5-flash-lite` | Research, Script (three agents), Voice, direction | 17 | 5 | 2.6 | 2824 | 1170 |
| `gemini-3.7-flash` | Research, Script (three agents), direction | 0 | 41 | never answered |  |  |
| `gemini-3.8-flash` | Research, Script (three agents), direction | 0 | 46 | never answered |  |  |
| `gemini-3.8-flash-lite-tts` | Experiments (E2, E4), Voice | 13 | 35 | 3.6 | 229 | 1599 |
| `gemini-3.8-flash-tts` | Voice | 14 | 44 | 5.0 | 481 | 3704 |
| `macos-say` | Voice | 2 | 0 | 1.4 |  |  |
| `wan-2.2-ti2v-5b (Kaggle T4)` | video | 6 | 0 | 3911.9 |  |  |
| `web-page` | Research | 2 | 0 | 0.8 |  |  |
| `wikidata-entity` | Research | 2 | 0 | 2.7 |  |  |
| `wikipedia-api` | Research | 2 | 0 | 1.1 |  |  |

## Why calls failed

| Reason | Attempts |
| --- | --- |
| quota or rate limit (HTTP 429) | 126 |
| model overloaded (HTTP 503) | 73 |
| other | 40 |
| timed out | 9 |
| reply failed a check | 1 |

## Free-tier limits met

These are what the log shows, not what the providers publish. The published limits still need to be read and added here.

- Gemini text (`gemini-3.8-flash`, `gemini-3.7-flash`): refused with "quota exceeded" or "high demand" on every attempt so far; `gemini-3.5-flash` answered every time it was reached.
- Gemini voice: a few calls a minute. A burst of ten lines was refused nine times; waiting 20 to 40 seconds cleared it.
- Lyria music models: refused with "quota exceeded" on the first call, so they are not available on the free tier.
- Cloudflare Workers AI: 71 pictures made without a refusal.

## List-price equivalent

Not yet worked out. The token counts and call counts above are what a price would be multiplied by; the providers' current price lists have not been read into this repo, and no price is stated here from memory.
