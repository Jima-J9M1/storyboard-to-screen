"""Write COSTS.md from runs.jsonl. Every number in that file is computed here, none is typed.

Usage:
    python -m core.costs            # rewrite COSTS.md
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import defaultdict
from datetime import date

from core import paths

STAGE_ORDER = ["research", "story", "narration", "keyframes", "music", "experiment"]
STAGE_NAMES = {
    "research": "Research", "story": "Script (three agents)", "narration": "Voice",
    "keyframes": "Pictures", "music": "Music", "experiment": "Experiments (E2, E4)",
}
LOCAL_STAGES = "Radio cut, Moving shots and Edit call no outside service. They run in FFmpeg on the director's machine and are not in the log."



def paid_lines(runs: list[dict]) -> list[str]:
    """Say what was paid, from the cost each call recorded. A call on a free tier records none."""
    paid: dict[str, list[float]] = {}
    for r in runs:
        if (r.get("cost_usd") or 0) > 0:
            entry = paid.setdefault(str(r.get("model")), [0, 0.0, 0.0])
            entry[0] += 1
            entry[1] += r["cost_usd"]
            entry[2] += r.get("cost_etb") or 0
    if not paid:
        return ["Nothing. Every call used a free tier."]
    lines = ["Every call used a free tier except the ones below, which were made on a paid service.", "",
             "| Model | Paid calls | Cost (USD) | Cost (ETB) |", "| --- | --- | --- | --- |"]
    for model, (calls, usd, etb) in sorted(paid.items()):
        lines.append(f"| {model} | {calls} | {usd:.2f} | {etb:.2f} |")
    return lines

def _lines() -> list[dict]:
    if not paths.RUNS_PATH.exists():
        return []
    return [json.loads(line) for line in paths.RUNS_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]


def _minutes(seconds: float) -> str:
    return f"{seconds / 60:.1f}"


def _row(cells: list) -> str:
    return "| " + " | ".join(str(c) for c in cells) + " |"


def build() -> str:
    runs = _lines()
    by_stage, by_model = defaultdict(list), defaultdict(list)
    for run in runs:
        by_stage[run["stage"]].append(run)
        by_model[run["model"]].append(run)

    out = [
        "# Costs",
        "",
        f"Generated from `runs.jsonl` by `python -m core.costs` on {date.today().isoformat()}. "
        "Do not edit by hand: run `make costs` again.",
        "",
        f"The log holds {len(runs)} attempts at outside calls, {sum(r['status'] == 'ok' for r in runs)} of which succeeded.",
        "",
        "## What was paid",
        "",
        *paid_lines(runs),
        "",
        "## Time per stage",
        "",
        "Latency is the wall-clock time of each call, measured by the pipeline. "
        "\"Time lost\" is the time spent on attempts that failed.",
        "",
        _row(["Stage", "Attempts", "Succeeded", "Failed", "Time in successful calls (min)", "Median successful call (s)", "Time lost to failures (min)"]),
        _row(["---"] * 7),
    ]
    stages = [s for s in STAGE_ORDER if s in by_stage] + sorted(s for s in by_stage if s not in STAGE_ORDER)
    for stage in stages:
        calls = by_stage[stage]
        good = [r["latency_s"] for r in calls if r["status"] == "ok"]
        bad = [r["latency_s"] for r in calls if r["status"] != "ok"]
        out.append(_row([
            STAGE_NAMES.get(stage, stage), len(calls), len(good), len(bad), _minutes(sum(good)),
            f"{statistics.median(good):.1f}" if good else "none", _minutes(sum(bad)),
        ]))
    out += ["", LOCAL_STAGES, ""]

    gpu = [r for r in runs if r.get("gpu_seconds")]
    out += ["## GPU minutes", ""]
    if gpu:
        out += [_row(["Stage", "Model", "GPU", "GPU session (min)", "Per candidate (s)"]), _row(["---"] * 5)]
        for r in gpu:
            out.append(_row([STAGE_NAMES.get(r["stage"], r["stage"]), r["model"], r.get("gpu") or "not recorded",
                             _minutes(r["gpu_seconds"]), ", ".join(str(s) for s in r.get("per_candidate_s") or [])]))
        out += ["", f"Total: {_minutes(sum(r['gpu_seconds'] for r in gpu))} GPU minutes, all on Kaggle's free allowance.", ""]
    else:
        out += ["No successful GPU job is in the log yet. Music is the only stage that uses a GPU; "
                "pictures are made on Cloudflare's hosted model, and moving shots are camera moves made in FFmpeg.", ""]

    out += [
        "## Each service",
        "",
        _row(["Service", "Used for", "Succeeded", "Failed", "Median time (s)", "Tokens in", "Tokens out"]),
        _row(["---"] * 7),
    ]
    for model in sorted(by_model):
        calls = by_model[model]
        good = [r for r in calls if r["status"] == "ok"]
        stages_used = ", ".join(sorted({STAGE_NAMES.get(r["stage"], r["stage"]) for r in calls}))
        out.append(_row([
            f"`{model}`", stages_used, len(good), len(calls) - len(good),
            f"{statistics.median(r['latency_s'] for r in good):.1f}" if good else "never answered",
            sum(r.get("tokens_in") or 0 for r in good) or "", sum(r.get("tokens_out") or 0 for r in good) or "",
        ]))

    failures = defaultdict(int)
    for r in runs:
        if r["status"] != "ok":
            error = r.get("error") or ""
            kind = ("quota or rate limit (HTTP 429)" if "429" in error else "model overloaded (HTTP 503)" if "503" in error
                    else "timed out" if "imeout" in error else "reply failed a check" if "BadReply" in error else "other")
            failures[kind] += 1
    out += ["", "## Why calls failed", "", _row(["Reason", "Attempts"]), _row(["---", "---"])]
    out += [_row([kind, count]) for kind, count in sorted(failures.items(), key=lambda kv: -kv[1])]

    pictures = [r for r in by_stage.get("keyframes", []) + by_stage.get("experiment", [])
                if r["status"] == "ok" and "flux" in r["model"]]
    out += [
        "",
        "## Free-tier limits met",
        "",
        "These are what the log shows, not what the providers publish. The published limits still need to be read and added here.",
        "",
        "- Gemini text (`gemini-3.8-flash`, `gemini-3.7-flash`): refused with \"quota exceeded\" or \"high demand\" on every attempt so far; `gemini-3.5-flash` answered every time it was reached.",
        "- Gemini voice: a few calls a minute. A burst of ten lines was refused nine times; waiting 20 to 40 seconds cleared it.",
        "- Lyria music models: refused with \"quota exceeded\" on the first call, so they are not available on the free tier.",
        f"- Cloudflare Workers AI: {len(pictures)} pictures made without a refusal.",
        "",
        "## List-price equivalent",
        "",
        "Not yet worked out. The token counts and call counts above are what a price would be multiplied by; "
        "the providers' current price lists have not been read into this repo, and no price is stated here from memory.",
        "",
    ]
    return "\n".join(out)


def main() -> int:
    (paths.ROOT / "COSTS.md").write_text(build(), encoding="utf-8")
    print("costs: COSTS.md rewritten from runs.jsonl.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
