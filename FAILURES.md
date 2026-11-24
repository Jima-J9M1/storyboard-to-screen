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

**What fixed it.** The model fallback. The model that actually answered is saved in `research/gebisa-ejeta/facts.json`, so the record shows which model wrote the facts.

**Evidence.** `runs.jsonl`, stage `research`, item `facts`: twelve `error` lines followed by one `ok` line for `gemini-3.5-flash`.

**What it taught us.** The newest free model is the busiest one. A retry on the same model does not help during a demand spike; a different model does.
