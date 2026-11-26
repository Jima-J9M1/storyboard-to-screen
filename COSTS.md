# Costs

Generated from `runs.jsonl` by `python -m core.costs` on 2026-11-26. Do not edit by hand: run `make costs` again.

The log holds 532 attempts at outside calls, 230 of which succeeded.

## What was paid

Every call used a free tier except the ones below, which were made on a paid service.

| Model | Paid calls | Cost (USD) | Cost (ETB) |
| --- | --- | --- | --- |
| addis-voices-2:am-yohanes-calm | 22 | 0.07 | 11.25 |

## Time per stage

Latency is the wall-clock time of each call, measured by the pipeline. "Time lost" is the time spent on attempts that failed.

| Stage | Attempts | Succeeded | Failed | Time in successful calls (min) | Median successful call (s) | Time lost to failures (min) |
| --- | --- | --- | --- | --- | --- | --- |
| Research | 52 | 11 | 41 | 3.6 | 3.3 | 8.2 |
| Script (three agents) | 103 | 12 | 91 | 3.7 | 12.3 | 26.4 |
| Voice | 247 | 94 | 153 | 7.0 | 4.0 | 5.3 |
| Pictures | 89 | 87 | 2 | 14.8 | 9.0 | 0.6 |
| Music | 5 | 3 | 2 | 12.1 | 352.7 | 53.5 |
| Experiments (E2, E4) | 14 | 13 | 1 | 1.1 | 3.7 | 0.0 |
| direction | 12 | 2 | 10 | 0.1 | 2.1 | 0.2 |
| video | 10 | 8 | 2 | 569.2 | 3911.9 | 2.3 |

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
| Music | ace-step-1.5-turbo (Kaggle T4) | Tesla T4, 15360 MiB | 5.0 | 16.6, 7.9, 7.9 |
| video | wan-2.2-ti2v-5b (Kaggle T4) | Tesla T4, 15360 MiB | 153.3 | 736.0, 731.8, 730.4, 731.3, 730.9, 730.4, 730.6, 731.6, 732.2, 731.3, 732.7, 730.9 |
| video | wan-2.2-ti2v-5b (Kaggle T4) | Tesla T4, 15360 MiB | 166.9 | 792.8, 801.2, 800.6, 801.3, 801.7, 801.0, 801.3, 802.5, 801.1, 801.8, 800.4, 800.8 |

Total: 1032.9 GPU minutes, all on Kaggle's free allowance.

## Each service

| Service | Used for | Succeeded | Failed | Median time (s) | Tokens in | Tokens out |
| --- | --- | --- | --- | --- | --- | --- |
| `@cf/black-forest-labs/flux-2-klein-4b` | Experiments (E2, E4), Pictures | 91 | 2 | 9.0 |  |  |
| `ace-step-1.5-turbo (Kaggle T4)` | Music | 3 | 2 | 352.7 |  |  |
| `addis-voices-2:am-yohanes-calm` | Voice | 22 | 30 | 4.2 |  |  |
| `gemini-3.1-flash-lite` | Script (three agents) | 0 | 6 | never answered |  |  |
| `gemini-3.1-flash-tts-preview` | Voice | 7 | 16 | 6.8 | 335 | 1636 |
| `gemini-3.5-flash` | Experiments (E2, E4), Research, Script (three agents), Voice, direction | 32 | 52 | 5.0 | 18262 | 9737 |
| `gemini-3.5-flash-lite` | Research, Script (three agents), Voice, direction | 32 | 9 | 2.6 | 5878 | 2661 |
| `gemini-3.7-flash` | Research, Script (three agents), direction | 0 | 50 | never answered |  |  |
| `gemini-3.8-flash` | Research, Script (three agents), direction | 0 | 54 | never answered |  |  |
| `gemini-3.8-flash-lite-tts` | Experiments (E2, E4), Voice | 13 | 35 | 3.6 | 229 | 1599 |
| `gemini-3.8-flash-tts` | Voice | 14 | 44 | 5.0 | 481 | 3704 |
| `macos-say` | Voice | 2 | 0 | 1.4 |  |  |
| `wan-2.2-ti2v-5b (Kaggle T4)` | video | 8 | 2 | 3911.9 |  |  |
| `web-page` | Research | 2 | 0 | 0.8 |  |  |
| `wikidata-entity` | Research | 2 | 0 | 2.7 |  |  |
| `wikipedia-api` | Research | 2 | 0 | 1.1 |  |  |

## Why calls failed

| Reason | Attempts |
| --- | --- |
| quota or rate limit (HTTP 429) | 150 |
| model overloaded (HTTP 503) | 93 |
| other | 42 |
| timed out | 10 |
| reply failed a check | 7 |

## Free-tier limits met

These are what the log shows, not what the providers publish. The published limits still need to be read and added here.

- Gemini text (`gemini-3.8-flash`, `gemini-3.7-flash`): refused with "quota exceeded" or "high demand" on every attempt so far; `gemini-3.5-flash` answered every time it was reached.
- Gemini voice: a few calls a minute. A burst of ten lines was refused nine times; waiting 20 to 40 seconds cleared it.
- Lyria music models: refused with "quota exceeded" on the first call, so they are not available on the free tier.
- Cloudflare Workers AI: 91 pictures made without a refusal.

## List-price equivalent

Not yet worked out. The token counts and call counts above are what a price would be multiplied by; the providers' current price lists have not been read into this repo, and no price is stated here from memory.
