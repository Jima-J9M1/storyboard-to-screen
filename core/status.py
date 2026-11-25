"""Report where every film is, as JSON, from the files in the repo.

This is the single place that decides what "done" means for a stage. The frontend shows
what this prints and adds nothing of its own. It only reads: no writes, no model calls.

Usage:
    python -m core.status                      # every film, one summary each, plus the repo's paperwork
    python -m core.status --film gebisa-ejeta  # one film in full
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
from pathlib import Path

from core import paths
from core.contracts import ValidationError, film_duration_s, load_brief, load_storyboard
from core.files import load_json

REQUIRED_DOCS = [
    ("README.md", "How to run it, and what it costs"),
    ("DESIGN.md", "Audience, intent and the two user tests"),
    ("ARCHITECTURE.md", "Stages, contracts, caching, failure handling"),
    ("EXPERIMENTS.md", "Hypothesis, change, result"),
    ("FAILURES.md", "What broke and what fixed it"),
    ("COSTS.md", "Latency and GPU minutes per stage"),
    ("ETHICS.md", "Consent, licences, labelling"),
]
EXPERIMENT_TARGET = 10
RECENT_RUNS = 300
# The name each stage's calls are logged under in runs.jsonl. Stages not listed call nothing outside.
LOG_NAMES = {"research": "research", "script": "story", "keyframes": "keyframes", "shots": "video", "music": "music", "narration": "narration"}

# (id, name shown, the module that implements it, the outputs folder it fills, the command that runs it)
STAGES = [
    ("intent", "Intent", None, None, None),
    ("research", "Research", "agents/researcher.py", None, "make research"),
    ("script", "Script", "agents/story.py", None, "make story"),
    ("radio_cut", "Radio cut", "pipeline/radio_cut.py", "radio_cut", "make radio"),
    ("keyframes", "Pictures", "pipeline/keyframes.py", "keyframes", "make keyframes"),
    ("shots", "Moving shots", "pipeline/shots.py", "shots", "make shots"),
    ("music", "Music", "pipeline/music.py", "music", "make music"),
    ("narration", "Voice", "pipeline/narration.py", "narration", "make narration"),
    ("assembly", "Edit", "pipeline/assemble.py", "film", "make assemble"),
]

# The file or files each shot must have before a per-shot stage counts as done.
PER_SHOT = {
    "keyframes": ["keyframes/{shot}.jpg"],
    "shots": ["shots/{shot}.9x16.mp4", "shots/{shot}.16x9.mp4"],
    "narration": ["narration/{shot}.{language}.wav"],
}

# What each stage is, in plain words: who does the work, what happens, and the director's part.
# who is "you" (the director), "agent" (a language model drafts it) or "code" (it is rendered).
GUIDE = {
    "intent": ("you", "You",
               "Decide who the film is for and the one thing they should feel at the end. "
               "Every later choice is judged against this.",
               "Write the audience and the feeling in the brief."),
    "research": ("agent", "Agent",
                 "The Researcher reads Wikipedia and any pages you list, then writes down the facts. "
                 "Each fact must quote its source, and code checks that the quote is really there.",
                 "Read the facts. If they are thin, add a page you trust to the brief and run it again."),
    "script": ("agent", "Agents draft, you direct",
               "Agents turn the facts into a storyboard: 8 to 12 shots, each with a narration line, "
               "a picture, a movement and a reason for being in the film.",
               "This is where you direct. Read the draft, rewrite any line, cut or reorder shots, "
               "and approve it. Nothing is generated from a storyboard you have not approved."),
    "radio_cut": ("code", "Code, then your testers",
                  "The narration is spoken by a text-to-speech voice over placeholder music on a black "
                  "screen. It tests the story before any picture is made.",
                  "Play it to three people from your audience and change the storyboard because of what they say."),
    "keyframes": ("code", "Code, you approve",
                  "One still picture is made for each shot, all against one reference sheet so the "
                  "look stays the same from shot to shot.",
                  "Accept or reject each picture before GPU time is spent turning it into video."),
    "shots": ("code", "Code",
              "Each picture becomes a moving clip. A video model on a Kaggle GPU animates the picture; "
              "where it has not made a clip, or failed, the shot gets a slow camera move over the picture instead.",
              "Watch every clip. Generated motion can distort hands and feet; send a bad one back by changing its seed."),
    "music": ("code", "Code, you choose",
              "Three candidate scores are generated from the music notes in the storyboard.",
              "Listen to them under the narration, choose one and write down why."),
    "narration": ("code", "Code",
                  "The final voice is generated, one audio file for each shot in each language.",
                  "Listen for names and places that are pronounced wrongly."),
    "assembly": ("code", "Code, then your testers",
                 "The shots are cut together, the music is lowered under the voice, subtitles are added, "
                 "the made-with-AI end card goes on, and the film is exported tall and wide.",
                 "Show it to three people from your audience, make the last changes, then publish."),
}


def _read_json(path: Path):
    return load_json(path) if path.exists() else None


def _brief(film: paths.Film) -> tuple[dict | None, list[str]]:
    """The brief as written, and what is wrong with it (if anything)."""
    raw = _read_json(film.brief)
    try:
        load_brief(film.brief)
        return raw, []
    except ValidationError as err:
        return raw, err.problems


def _storyboard(film: paths.Film) -> tuple[dict | None, list[str]]:
    if not film.storyboard.exists():
        return None, []
    try:
        return load_storyboard(film.storyboard), []
    except ValidationError as err:
        return None, err.problems


def _research(film: paths.Film) -> dict:
    sources = []
    for path in sorted(film.research.glob("source_*.json")) if film.research.is_dir() else []:
        record = load_json(path)
        sources.append({
            "source_id": record["source_id"],
            "title": record.get("title"),
            "url": record.get("permalink") or record.get("url"),
            "licence": record.get("licence"),
            "retrieved_at": record.get("retrieved_at"),
            "words": record.get("words") or len(record.get("text", "").split()),
        })
    sources.sort(key=lambda src: (src["source_id"] != "wikipedia", src["source_id"]))
    facts = _read_json(film.research / "facts.json") or {}
    return {
        "subject": _read_json(film.research / "subject.json"),
        "sources": sources,
        "facts": facts.get("facts", []),
        "facts_model": facts.get("model"),
    }


def _run_lines(slug: str | None = None) -> list[dict]:
    """The run log, for one film or for the whole repo."""
    lines = []
    if paths.RUNS_PATH.exists():
        for line in paths.RUNS_PATH.read_text(encoding="utf-8").splitlines():
            if line.strip():
                run = json.loads(line)
                if slug is None or run.get("film") == slug:
                    lines.append(run)
    return lines


def _runs(slug: str) -> dict:
    lines = _run_lines(slug)
    by_model: dict[str, dict] = {}
    for run in lines:
        entry = by_model.setdefault(run["model"], {
            "model": run["model"], "kind": run.get("kind"), "ok": 0, "failed": 0, "latencies": [],
        })
        if run["status"] == "ok":
            entry["ok"] += 1
            entry["latencies"].append(run["latency_s"])
        else:
            entry["failed"] += 1
    models = []
    for entry in by_model.values():
        latencies = entry.pop("latencies")
        entry["median_latency_s"] = round(statistics.median(latencies), 2) if latencies else None
        models.append(entry)

    return {
        "attempts": len(lines),
        "ok": sum(r["status"] == "ok" for r in lines),
        "failed": sum(r["status"] != "ok" for r in lines),
        "model_calls": sum(r.get("kind") == "model" and r["status"] == "ok" for r in lines),
        "cost_usd": round(sum(r.get("cost_usd") or 0 for r in lines), 4),
        "models": sorted(models, key=lambda m: m["model"]),
        "recent": [
            {
                "ts": r["ts"], "stage": r["stage"], "item": r.get("item"), "model": r["model"],
                "attempt": r["attempt"], "status": r["status"], "latency_s": r["latency_s"],
                "error": (r.get("error") or "").split("\n")[0][:140],
            }
            for r in reversed(lines[-RECENT_RUNS:])
        ],
    }


def _output_count(film: paths.Film, folder: str | None) -> int:
    if not folder:
        return 0
    path = film.outputs / folder
    return sum(1 for p in path.iterdir() if p.is_file() and not p.name.startswith(".")) if path.is_dir() else 0


def _calls(lines: list[dict], log_name: str | None) -> dict | None:
    """How a stage's outside calls went. None for a stage that makes no outside calls."""
    if log_name is None:
        return None
    mine = [r for r in lines if r["stage"] == log_name]
    good = [r for r in mine if r["status"] == "ok"]
    return {
        "log_name": log_name, "attempts": len(mine), "ok": len(good), "failed": len(mine) - len(good),
        "seconds": round(sum(r["latency_s"] for r in good), 1),
        "models": sorted({r["model"] for r in good}),
    }


def _stages(film: paths.Film, brief_problems: list[str], research: dict,
            board: dict | None, board_problems: list[str]) -> list[dict]:
    """Each stage with a status: done, blocked, ready or waiting. At most one stage is 'current'."""
    shots = len(board["shots"]) if board else 0
    lines = _run_lines(film.slug)
    stages = []
    for stage_id, name, module, folder, command in STAGES:
        built = module is None or (paths.ROOT / module).exists()
        made = _output_count(film, folder)
        done, detail, problems = False, "", []

        if stage_id == "intent":
            done, problems = not brief_problems, brief_problems
            detail = "Audience and feeling are written." if done else "The brief is not finished."
        elif stage_id == "research":
            done = bool(research["facts"])
            detail = (f"{len(research['facts'])} facts from {len(research['sources'])} sources."
                      if done else "No facts yet.")
        elif stage_id == "script":
            done, problems = board is not None, board_problems
            if done:
                detail = f"{shots} shots, {film_duration_s(board):g} seconds."
            elif board_problems:
                detail = "storyboard.json does not pass validation."
            else:
                detail = "No storyboard yet."
        elif stage_id in PER_SHOT:
            # Count the shots that have their file, not the files in the folder: the folder
            # also holds the reference sheet, a contact sheet and a timings record.
            language = board["languages"][0] if board else ""
            made = sum(
                all((film.outputs / pattern.format(shot=shot["id"], language=language)).exists()
                    for pattern in PER_SHOT[stage_id])
                for shot in (board["shots"] if board else [])
            )
            done = made >= shots > 0
            detail = f"{made} of {shots} shots have theirs." if made else "Nothing made yet."
        else:
            done = made > 0
            detail = f"{made} file{'s' if made != 1 else ''} made." if made else "Nothing made yet."

        if not built and not done:
            detail = "This stage is not built yet."
        who, who_label, what, your_part = GUIDE[stage_id]
        stages.append({
            "id": stage_id, "name": name, "built": built, "done": done, "detail": detail,
            "problems": problems, "who": who, "who_label": who_label, "what": what, "your_part": your_part,
            "calls": _calls(lines, LOG_NAMES.get(stage_id)),
            "command": f"{command} FILM={film.slug}" if command and built else None,
        })

    current_found = False
    for stage in stages:
        stage["current"] = False
        if stage["done"]:
            stage["status"] = "done"
        elif not current_found:
            current_found = True
            stage["current"] = True
            stage["status"] = "blocked" if stage["problems"] or not stage["built"] else "ready"
        else:
            stage["status"] = "waiting"
    return stages


def _file(film: paths.Film, relative: str) -> dict | None:
    """A file under the film's outputs folder, if it exists. `v` changes whenever the file does."""
    path = film.outputs / relative
    if not path.is_file():
        return None
    stat = path.stat()
    return {"path": relative, "v": int(stat.st_mtime), "bytes": stat.st_size}


def _outputs(film: paths.Film, board: dict | None) -> dict:
    """Everything the stages have made for this film, so it can be looked at and listened to."""
    timings = {(t["shot"], t["language"]): t for t in _read_json(film.outputs / "narration" / "timings.json") or []}
    moves = {m["shot"]: m for m in _read_json(film.outputs / "shots" / "moves.json") or []}
    shots = {}
    for shot in (board or {}).get("shots", []):
        sid = shot["id"]
        narration = {}
        for language in board["languages"]:
            audio_file = _file(film, f"narration/{sid}.{language}.wav")
            if audio_file:
                timing = timings.get((sid, language), {})
                narration[language] = audio_file | {
                    "spoken_s": timing.get("spoken_s"), "fits": timing.get("fits"),
                    "model": timing.get("model"), "heard": timing.get("heard"),
                    "matches_line": timing.get("matches_line"),
                }
        shots[sid] = {
            "picture": _file(film, f"keyframes/{sid}.jpg"),
            "narration": narration,
            "clips": {shape: _file(film, f"shots/{sid}.{shape}.mp4") for shape in ("9x16", "16x9")},
            "generated": {shape: _file(film, f"video/{sid}.{shape}.mp4") for shape in ("9x16", "16x9")},
            "move": moves.get(sid, {}).get("move"),
        }

    music = (board or {}).get("music", {})
    job = _read_json(film.outputs / "music" / "job_report.json") or {}
    took = {c["seed"]: c["seconds"] for c in job.get("candidates", [])}
    candidates = [
        found | {"seed": seed, "seconds_to_make": took.get(seed),
                 "audition": _file(film, f"music/audition_{seed}.m4a")}
        for seed in music.get("seeds", [])
        if (found := _file(film, f"music/candidate_{seed}.m4a"))
    ]

    # Recordings of the same lines by different voices, kept side by side so they can be compared.
    compare = {}
    compare_dir = film.outputs / "voice_compare"
    for folder in sorted(p for p in compare_dir.iterdir() if p.is_dir()) if compare_dir.is_dir() else []:
        timings = {t["shot"]: t for t in _read_json(folder / "timings.json") or []}
        lines = {}
        for shot in (board or {}).get("shots", []):
            found = _file(film, f"voice_compare/{folder.name}/{shot['id']}.{board['languages'][0]}.wav")
            if found:
                timing = timings.get(shot["id"], {})
                lines[shot["id"]] = found | {"spoken_s": timing.get("spoken_s"), "model": timing.get("model")}
        if lines:
            compare[folder.name] = lines

    report = _read_json(film.outputs / "film" / "report.json") or {}
    films = {}
    for shape, facts in report.get("films", {}).items():
        found = _file(film, f"film/{facts['file']}")
        if found:
            films[shape] = found | {k: facts[k] for k in ("duration_s", "loudness_lufs", "true_peak_db", "subtitle_cards")}

    return {
        "reference": _file(film, "keyframes/reference.jpg"),
        "contact_sheet": _file(film, "keyframes/contact_sheet.jpg"),
        "shots": shots,
        "voice_compare": compare,
        "radio_cut": {"audio": _file(film, "radio_cut/radio_cut.m4a"), "video": _file(film, "radio_cut/radio_cut.mp4")},
        "music": {"candidates": candidates, "chosen_seed": music.get("chosen_seed"),
                  "gpu": job.get("gpu"), "gpu_seconds": job.get("total_seconds")},
        "film": {"shapes": films, "placeholder_music": report.get("placeholder_music"), "music": report.get("music")},
    }


def film_state(slug: str) -> dict:
    """Everything about one film."""
    film = paths.film(slug)
    if not film.brief.exists():
        raise SystemExit(f"There is no film named \"{slug}\".")
    brief, brief_problems = _brief(film)
    research = _research(film)
    board, board_problems = _storyboard(film)
    return {
        "slug": slug,
        "brief": brief,
        "stages": _stages(film, brief_problems, research, board, board_problems),
        "research": research,
        "storyboard": board,
        "outputs": _outputs(film, board),
        "runs": _runs(slug),
    }


def _entries(doc: str) -> list[str]:
    """The titles of the '## ' entries in a log document."""
    path = paths.ROOT / doc
    if not path.exists():
        return []
    return re.findall(r"^## (.+)$", path.read_text(encoding="utf-8"), flags=re.MULTILINE)


def repo_state() -> dict:
    """Every film in brief, and the paperwork that belongs to the repo as a whole."""
    films = []
    for slug in paths.film_slugs():
        state = film_state(slug)
        current = next((s for s in state["stages"] if s["current"]), None)
        films.append({
            "slug": slug,
            "title": (state["brief"] or {}).get("title") or slug,
            "languages": (state["brief"] or {}).get("languages") or [],
            "poster": next((shot["picture"] for shot in state["outputs"]["shots"].values() if shot["picture"]), None),
            "has_film": bool(state["outputs"]["film"]["shapes"]),
            "description": (state["research"]["subject"] or {}).get("description"),
            "stages": [{"id": s["id"], "name": s["name"], "status": s["status"], "who": s["who"]} for s in state["stages"]],
            "done": sum(s["done"] for s in state["stages"]),
            "total": len(state["stages"]),
            "current": current and {"name": current["name"], "status": current["status"],
                                    "detail": current["detail"], "who": current["who"]},
            "attempts": state["runs"]["attempts"],
            "failed": state["runs"]["failed"],
        })
    return {
        "films": films,
        "docs": [{"name": name, "purpose": purpose, "exists": (paths.ROOT / name).exists()}
                 for name, purpose in REQUIRED_DOCS],
        "experiments": {"titles": _entries("EXPERIMENTS.md"), "target": EXPERIMENT_TARGET},
        "failures": {"titles": _entries("FAILURES.md")},
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--film", help="one film in full; without it, a summary of every film")
    args = parser.parse_args()
    state = film_state(args.film) if args.film else repo_state()
    json.dump(state, sys.stdout, ensure_ascii=False, indent=2)
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
