"""Reviser: change one thing in a storyboard from the director's note, then remake just that thing.

The director looks at what a stage made and says, in their own words, what is wrong and how
to fix it. The Reviser rewrites the one field of the storyboard that produced it, keeps a
record of the note and the change, and runs the stage for that one item.

What can be directed:
    picture  a shot's picture description     then that one picture is repainted
    line     a shot's narration line          then that one line is re-recorded and the shots re-timed
    motion   a shot's motion description      the clip is remade the next time the video stage runs
    score    the brief for the music          the candidates are remade the next time the music stage runs
    look     the style shared by all pictures then every picture is repainted
    world    who and where, for all pictures  then every picture is repainted

Every note is appended to films/<slug>/direction.jsonl with the text before and after, so
the film's history shows who decided what. `--reroll` asks for another version of a picture
without changing its description, by moving to the next seed.

Usage:
    python -m agents.reviser --film gebisa-ejeta --target picture --shot s08 --note "There are three hands. Show only two."
    python -m agents.reviser --film gebisa-ejeta --target picture --shot s08 --reroll
    python -m agents.reviser --film gebisa-ejeta --target line --shot s02 --note "Do not say constantly."
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from agents.story import LANGUAGE_NAMES, LINES_SCHEMA, MAX_LINE_WORDS, MIN_LINE_WORDS, translation_problems, _name_words, subject_name
from core import llm, paths
from core.contracts import ValidationError, load_brief, load_storyboard
from core.files import load_json, write_json
from core.runlog import set_film

STAGE = "direction"
PROMPTS = Path(__file__).parent / "prompts"
TARGETS = {
    "picture": "a picture description for one shot",
    "line": "a narration line for one shot, in English",
    "motion": "a description of what moves in one shot and how the camera moves",
    "score": "the brief for the film's instrumental score",
    "look": "the style shared by every picture in the film",
    "world": "the rules for how the film's people, homes, land and crops look when they appear",
}
PER_SHOT = ("picture", "line", "motion")
REVISED_SCHEMA = {
    "type": "object", "required": ["revised", "what_changed"], "additionalProperties": False,
    "properties": {"revised": {"type": "string", "minLength": 10}, "what_changed": {"type": "string", "minLength": 5}},
}


class CannotDirect(Exception):
    """The request cannot be carried out as given. The message says why, for the director."""


def _shot(board: dict, shot_id: str | None) -> dict:
    for shot in board["shots"]:
        if shot["id"] == shot_id:
            return shot
    raise CannotDirect(f"There is no shot called \"{shot_id}\" in this film.")


def current_text(board: dict, target: str, shot_id: str | None) -> str:
    if target == "picture":
        return _shot(board, shot_id)["image_prompt"]
    if target == "line":
        return _shot(board, shot_id)["subtitle_en"]
    if target == "motion":
        return _shot(board, shot_id)["motion_prompt"]
    if target == "score":
        return board["music"]["caption"]
    return board["style_block"] if target == "look" else board["world_block"]


def problems_with(revised: str, target: str, title: str, policy: str) -> list[str]:
    """The same rules the story agents are held to, applied to a revision."""
    problems = []
    if target in ("picture", "look", "world") and policy in ("no_likeness", "review"):
        if any(word in revised.lower() for word in _name_words(title)):
            problems.append("it names the film's subject, who may not be shown")
    if target == "line":
        words = len(revised.split())
        if not MIN_LINE_WORDS <= words <= MAX_LINE_WORDS:
            problems.append(f"the line has {words} words; it must be {MIN_LINE_WORDS}-{MAX_LINE_WORDS}")
        if any(mark in revised for mark in '"“”'):
            problems.append("the line uses quotation marks; the narration may not quote anyone")
    if target == "score" and "instrumental" not in revised.lower():
        problems.append("the score brief must say the score is instrumental")
    return problems


def revise(film: paths.Film, board: dict, brief: dict, target: str, shot_id: str | None, note: str) -> dict:
    """Ask the Reviser for new text. Returns the record that goes into the direction log."""
    subject = load_json(film.research / "subject.json") if (film.research / "subject.json").exists() else {}
    policy = subject.get("likeness_policy", "review")
    before = current_text(board, target, shot_id)
    context = [
        f"Film: {brief['title']}",
        f"Audience: {brief['audience']}",
        f"Feeling to leave them with: {brief['feeling']}",
        f"How the subject may be shown: {policy}. {subject.get('policy_reason', '')}",
        f"Who and where (applies to every picture): {board['world_block']}",
        f"The look of every picture: {board['style_block']}",
    ]
    if shot_id:
        shot = _shot(board, shot_id)
        context.append(f"This shot's narration: {shot['subtitle_en']}")
        context.append(f"Why this shot is in the film: {shot['reason']}")
        if target == "line":
            facts = {f["id"]: f["text"] for f in load_json(film.research / "facts.json")["facts"]}
            context.append("Facts this line may use: " + " ".join(facts[i] for i in shot["fact_ids"] if i in facts))
    prompt = (
        f"What it is: {TARGETS[target]}{f' (shot {shot_id})' if shot_id else ''}\n\n"
        f"Current text:\n{before}\n\nThe director's note:\n{note}\n\nThe film's rules and context:\n" + "\n".join(context)
    )
    reply, model = llm.generate_json(
        prompt, REVISED_SCHEMA, stage=STAGE, item=f"{target}{'.' + shot_id if shot_id else ''}",
        system=(PROMPTS / "reviser.md").read_text(encoding="utf-8"), temperature=0.4,
        check=lambda r: problems_with(r["revised"], target, subject_name(brief), policy),
    )
    return {"target": target, "shot": shot_id, "note": note, "before": before,
            "after": reply["revised"].strip(), "what_changed": reply["what_changed"].strip(), "model": model}


def translate_line(board: dict, english: str, language: str, item: str) -> str:
    """One narration line into the film's language, by the Translator's own instructions."""
    name = LANGUAGE_NAMES.get(language, language)
    reply, _ = llm.generate_json(
        f"Target language: {name} (code {language})\n\nEnglish lines:\n1. {english}", LINES_SCHEMA,
        stage=STAGE, item=item, system=(PROMPTS / "translator.md").read_text(encoding="utf-8"),
        temperature=0.4, check=lambda r: translation_problems(r, [english], language),
    )
    return reply["lines"][0]


def apply(board: dict, record: dict) -> None:
    """Write a revision into the storyboard."""
    target, after = record["target"], record["after"]
    if target in PER_SHOT:
        shot = _shot(board, record["shot"])
        if target == "picture":
            shot["image_prompt"] = after
        elif target == "motion":
            shot["motion_prompt"] = after
        else:
            shot["subtitle_en"] = after
            for language in board["languages"]:
                shot["narration"][language] = after if language == "en" else translate_line(
                    board, after, language, f"line.{record['shot']}.{language}")
            record["narration"] = dict(shot["narration"])
    elif target == "score":
        board["music"]["caption"] = after
        board["music"].pop("chosen_seed", None)   # the old choice was of candidates made from the old brief
    elif target == "look":
        board["style_block"] = after
    else:
        board["world_block"] = after


def remake(film: paths.Film, record: dict) -> str:
    """Run the stage for the one thing that changed. Returns a sentence saying what happened next."""
    target, shot_id = record["target"], record["shot"]
    if target in ("picture", "look", "world"):
        from pipeline import keyframes
        code = keyframes.run(film.slug, only=[shot_id] if target == "picture" else None)
        done = f"The picture for {shot_id} was repainted." if target == "picture" else "Every picture was repainted."
        if code != 0:
            return "The storyboard was changed, but the picture could not be repainted. Run make keyframes to try again."
        return done + " Its moving clip now comes from the old picture, so the shot uses a camera move until the video stage runs again."
    if target == "line":
        from pipeline import narration
        code = narration.run(film.slug, fit=True)
        if code != 0:
            return "The line was changed, but it could not be re-recorded yet. Run make narration to try again."
        return f"The line for {shot_id} was re-recorded and the shot lengths were set from the voice."
    if target == "motion":
        return f"The motion for {shot_id} was changed. Its clip is remade the next time the video stage runs (make video)."
    return "The score brief was changed and the old choice of score was cleared. New candidates are made by make music."


def direct(film_slug: str, target: str, shot_id: str | None, note: str, reroll: bool = False) -> dict:
    film = paths.film(film_slug)
    set_film(film.slug)
    brief = load_brief(film.brief)
    board = load_storyboard(film.storyboard, check_length=False)
    if target not in TARGETS:
        raise CannotDirect(f"\"{target}\" cannot be directed. Choose one of: {', '.join(TARGETS)}.")
    if target in PER_SHOT and not shot_id:
        raise CannotDirect(f"Say which shot: a {target} belongs to one shot.")
    if target not in PER_SHOT:
        shot_id = None

    if reroll:
        if target != "picture":
            raise CannotDirect("Only a picture can be tried again without a note.")
        shot = _shot(board, shot_id)
        record = {"target": "picture", "shot": shot_id, "note": "Try another version of this picture.",
                  "before": f"seed {shot['seed']}", "after": f"seed {shot['seed'] + 1}",
                  "what_changed": "The description is unchanged; the picture was made again from the next seed.", "model": None}
        shot["seed"] += 1
    else:
        if len(note.strip()) < 5:
            raise CannotDirect("Write a note saying what is wrong and how to fix it.")
        record = revise(film, board, brief, target, shot_id, note.strip())
        apply(board, record)

    write_json(film.storyboard, board)
    record = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **record}
    with (film.dir / "direction.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(record, ensure_ascii=False) + "\n")
    record["next"] = remake(film, record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--film", required=True, help="the film's folder name under films/")
    parser.add_argument("--target", required=True, choices=list(TARGETS))
    parser.add_argument("--shot", help="the shot id, for a picture, line or motion")
    parser.add_argument("--note", default="", help="what is wrong and how to fix it, in the director's words")
    parser.add_argument("--reroll", action="store_true", help="another version of a picture, without changing its description")
    parser.add_argument("--json", action="store_true", help="print the result as JSON (used by the production board)")
    args = parser.parse_args()
    try:
        record = direct(args.film, args.target, args.shot, args.note, args.reroll)
    except (CannotDirect, ValidationError) as err:
        print(json.dumps({"error": str(err)}) if args.json else str(err), file=sys.stdout if args.json else sys.stderr)
        return 1
    if args.json:
        print("@@RESULT@@" + json.dumps(record, ensure_ascii=False))
    else:
        print(f"Before: {record['before']}\nAfter:  {record['after']}\n{record['what_changed']}\n{record['next']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
