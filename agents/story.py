"""Story agents: draft a film's storyboard from its brief and researched facts.

Four agents run in order, and each owns part of the storyboard:
    Screenwriter       the narration line (in English) and source facts of every shot
    Translator         the narration in every other language the brief asks for
    Storyboard artist  the look of the film and the picture, movement and reason of every shot
    Composer           the brief for the score

Reads   films/<slug>/brief.json, films/<slug>/research/facts.json and subject.json
Writes  films/<slug>/draft/script.json, visuals.json, music.json   what each agent returned
        films/<slug>/storyboard.draft.json                         the three put together
        films/<slug>/storyboard.json                               only if the film has none yet

The director owns storyboard.json. Once it exists the agents never overwrite it: a new draft
goes to storyboard.draft.json, and the director copies across what they want, or passes
--replace to take the whole draft.

Each agent's reply is checked by code before it is saved (shot count, word count, running
time, that every cited fact exists, that the subject's name is not in a picture prompt).
A reply that fails is retried, like any other failed call.

Usage:
    python -m agents.story --film gebisa-ejeta
    python -m agents.story --film gebisa-ejeta --replace   # overwrite storyboard.json with the draft
    python -m agents.story --film gebisa-ejeta --refresh   # ask the agents again
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

from core import llm, paths
from core.cache import Cache
from core.contracts import MAX_FILM_S, MIN_FILM_S, ValidationError, load_brief, load_storyboard
from core.files import load_json, write_json
from core.runlog import set_film

STAGE = "story"
PROMPTS = Path(__file__).parent / "prompts"
SEED = 1
TEMPERATURE = 0.7

# How narration becomes running time. The rate is measured, not assumed: the narrator's
# voice spoke the first draft at 1.95 words a second (EXPERIMENTS.md, E3). Each shot also
# gets a short breath so lines do not run into each other.
WORDS_PER_SECOND = 1.95
BREATH_S = 0.8
MIN_SHOT_S, MAX_SHOT_S = 3.0, 12.0
MIN_WORDS, MAX_WORDS = 110, 155
MIN_LINE_WORDS, MAX_LINE_WORDS = 6, 24

END_CARD = {"text": "This film was made with AI.", "duration_s": 3}
VOICE = {"name": "Sulafat", "style": "calm, warm, unhurried"}  # the director can change both
SCORE_SEEDS = [1, 2, 3]          # three candidates for the director to choose from
REFERENCE_SEED = 7
FIRST_SHOT_SEED = 1001

SCRIPT_SCHEMA = {
    "type": "object", "required": ["shots"], "additionalProperties": False,
    "properties": {"shots": {"type": "array", "minItems": 8, "maxItems": 12, "items": {
        "type": "object", "required": ["beat", "narration", "fact_ids"], "additionalProperties": False,
        "properties": {
            "beat": {"type": "string", "minLength": 3},
            "narration": {"type": "string", "minLength": 10},
            "fact_ids": {"type": "array", "items": {"type": "string"}, "uniqueItems": True},
        }}}},
}
VISUALS_SCHEMA = {
    "type": "object", "required": ["style_block", "world_block", "reference_sheet_prompt", "shots"], "additionalProperties": False,
    "properties": {
        "style_block": {"type": "string", "minLength": 20},
        "world_block": {"type": "string", "minLength": 40},
        "reference_sheet_prompt": {"type": "string", "minLength": 20},
        "shots": {"type": "array", "items": {
            "type": "object", "required": ["size", "image_prompt", "motion_prompt", "reason"],
            "additionalProperties": False,
            "properties": {
                "size": {"enum": ["wide", "medium", "close"]},
                "image_prompt": {"type": "string", "minLength": 20},
                "motion_prompt": {"type": "string", "minLength": 5},
                "reason": {"type": "string", "minLength": 10},
            }}},
    },
}
LINES_SCHEMA = {
    "type": "object", "required": ["lines"], "additionalProperties": False,
    "properties": {"lines": {"type": "array", "items": {"type": "string", "minLength": 2}}},
}
LANGUAGE_NAMES = {"am": "Amharic", "om": "Afaan Oromo", "ti": "Tigrinya", "so": "Somali", "sw": "Swahili", "en": "English"}
# Languages written in Ge'ez script. A translation into one of them that is mostly Latin letters is wrong.
ETHIOPIC = {"am", "ti"}

MUSIC_SCHEMA = {
    "type": "object", "required": ["caption", "bpm", "key", "cues"], "additionalProperties": False,
    "properties": {
        "caption": {"type": "string", "minLength": 20},
        "bpm": {"type": "integer", "minimum": 60, "maximum": 100},
        "key": {"type": "string", "minLength": 1},
        "cues": {"type": "array", "minItems": 3, "maxItems": 5, "items": {
            "type": "object", "required": ["at_s", "note"], "additionalProperties": False,
            "properties": {"at_s": {"type": "number", "minimum": 0}, "note": {"type": "string", "minLength": 3}}}},
    },
}


# ---------- timing ----------

def shot_duration_s(narration: str) -> float:
    """How long a shot must be for its line to be spoken, to the nearest half second."""
    seconds = len(narration.split()) / WORDS_PER_SECOND + BREATH_S
    return min(MAX_SHOT_S, max(MIN_SHOT_S, math.ceil(seconds * 2) / 2))


def film_length_s(lines: list[str]) -> float:
    return sum(shot_duration_s(line) for line in lines) + END_CARD["duration_s"]


# ---------- checks on what the agents return ----------

def script_problems(reply: dict, fact_ids: set[str]) -> list[str]:
    problems = []
    lines = [shot["narration"] for shot in reply["shots"]]
    for n, shot in enumerate(reply["shots"], start=1):
        words = len(shot["narration"].split())
        if not MIN_LINE_WORDS <= words <= MAX_LINE_WORDS:
            problems.append(f"shot {n} has {words} words; each line must be {MIN_LINE_WORDS}-{MAX_LINE_WORDS}")
        unknown = [f for f in shot["fact_ids"] if f not in fact_ids]
        if unknown:
            problems.append(f"shot {n} cites facts that do not exist: {', '.join(unknown)}")
        if any(mark in shot["narration"] for mark in '"“”'):
            problems.append(f"shot {n} uses quotation marks; the narration may not quote anyone")
    total_words = sum(len(line.split()) for line in lines)
    if not MIN_WORDS <= total_words <= MAX_WORDS:
        problems.append(f"the narration has {total_words} words; it must be {MIN_WORDS}-{MAX_WORDS}")
    length = film_length_s(lines)
    if not MIN_FILM_S <= length <= MAX_FILM_S:
        problems.append(f"the film would run {length:g} s; it must be {MIN_FILM_S}-{MAX_FILM_S} s")
    if not any(shot["fact_ids"] for shot in reply["shots"]):
        problems.append("no shot cites a fact")
    return problems


def translation_problems(reply: dict, english: list[str], language: str) -> list[str]:
    problems = []
    lines = reply["lines"]
    if len(lines) != len(english):
        return [f"{len(lines)} translated lines for {len(english)} English lines; give exactly one each, in order"]
    for n, line in enumerate(lines, start=1):
        letters = [ch for ch in line if ch.isalpha()]
        if language in ETHIOPIC and letters:
            ethiopic = sum("\u1200" <= ch <= "\u139f" for ch in letters)
            if ethiopic / len(letters) < 0.8:
                problems.append(f"line {n} is not written in Ge'ez script")
        if any(mark in line for mark in '"“”'):
            problems.append(f"line {n} uses quotation marks")
    return problems


def _name_words(title: str) -> list[str]:
    return [word.lower() for word in title.split() if len(word) > 2]


def subject_name(brief: dict) -> str:
    """The name that may not appear in a picture prompt. A researched title is the subject's name.
    The title of a story the director told is a title, not a name ("The Last Buna"), so its
    words are ordinary words the pictures need; nobody's face is shown either way."""
    return "" if brief.get("story") else brief["title"]


def visuals_problems(reply: dict, shot_count: int, title: str, likeness_policy: str) -> list[str]:
    problems = []
    if len(reply["shots"]) != shot_count:
        problems.append(f"{len(reply['shots'])} pictures for {shot_count} shots; give exactly one per shot")
    sizes = [shot["size"] for shot in reply["shots"]]
    for size in ("wide", "medium", "close"):
        if sizes.count(size) < 2:
            problems.append(f"only {sizes.count(size)} {size} shot(s); use each size at least twice")
    # "review" is a real person who has died. Until the director records a decision in ETHICS.md
    # they are treated like a living one: not shown, and not named in a picture prompt.
    if likeness_policy in ("no_likeness", "review"):
        prompts = [("reference_sheet_prompt", reply["reference_sheet_prompt"])]
        prompts += [(f"shot {n} image_prompt", s["image_prompt"]) for n, s in enumerate(reply["shots"], start=1)]
        for where, prompt in prompts:
            if any(word in prompt.lower() for word in _name_words(title)):
                problems.append(f"{where} names the subject, who may not be shown")
    for n, shot in enumerate(reply["shots"], start=1):
        if len(shot["motion_prompt"].split()) > 16:
            problems.append(f"shot {n} motion_prompt is too long; give the camera movement only")
    return problems


def music_problems(reply: dict, shot_starts: list[float], film_s: float) -> list[str]:
    problems = []
    if "instrumental" not in reply["caption"].lower():
        problems.append("the caption must say the score is instrumental")
    times = [cue["at_s"] for cue in reply["cues"]]
    if times[0] != 0:
        problems.append("the first cue must be at 0")
    if times != sorted(times):
        problems.append("cues must be in time order")
    if times[-1] >= film_s:
        problems.append(f"the last cue is at {times[-1]:g} s but the film is {film_s:g} s long")
    return problems


# ---------- running one agent ----------

def ask(film: paths.Film, cache: Cache, name: str, prompt: str, schema: dict, check, refresh: bool,
        save_as: str | None = None) -> dict:
    """Ask one agent, or reuse its saved reply if its inputs have not changed.

    save_as  the name to file the reply under, when one agent is asked several times (once per language)
    """
    item = save_as or name
    out = film.dir / "draft" / f"{item}.json"
    system = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    key = llm.request_key(system, prompt, TEMPERATURE, SEED)
    if cache.fresh(item, key) and not refresh:
        print(f"story: {item} is up to date; no model call made.")
        return load_json(out)["reply"]
    reply, model = llm.generate_json(
        prompt, schema, stage=STAGE, item=item, system=system, key=key,
        temperature=TEMPERATURE, seed=SEED, check=check,
    )
    write_json(out, {"agent": name, "model": model, "seed": SEED, "temperature": TEMPERATURE, "reply": reply})
    cache.store(item, key, [out])
    print(f"story: {item} drafted by {model}.")
    return reply


def _intent(brief: dict) -> str:
    return f"Film title: {brief['title']}\nAudience: {brief['audience']}\nFeeling to leave them with: {brief['feeling']}"


# ---------- putting the storyboard together ----------

def assemble(brief: dict, script: dict, visuals: dict, music: dict,
             translations: dict[str, list[str]] | None = None) -> dict:
    """Put the agents' work together. translations maps a language code to one line per shot."""
    translations = translations or {}
    shots = []
    for n, (line, picture) in enumerate(zip(script["shots"], visuals["shots"]), start=1):
        narration = {lang: line["narration"] if lang == "en" else translations[lang][n - 1] for lang in brief["languages"]}
        shots.append({
            "id": f"s{n:02d}",
            # An estimate from the English word count. The voice stage's --fit replaces it with
            # the measured length of the spoken line, which matters most for other languages.
            "duration_s": shot_duration_s(line["narration"]),
            "size": picture["size"],
            "image_prompt": picture["image_prompt"],
            # Guided by the reference sheet, a wide landscape comes back as a copy of the sheet
            # (EXPERIMENTS.md, E4). Wide shots rely on the style block; the director can change this.
            "use_reference": picture["size"] != "wide",
            # Every shot starts as a pan and zoom over its picture, which needs no GPU.
            # The director changes chosen shots to "video" once the film works end to end.
            "motion_mode": "ken_burns",
            "motion_prompt": picture["motion_prompt"],
            "narration": narration,
            "subtitle_en": line["narration"],
            "reason": picture["reason"],
            "fact_ids": line["fact_ids"],
            "seed": FIRST_SHOT_SEED + n - 1,
        })
    return {
        "title": brief["title"],
        "languages": brief["languages"],
        "voice": VOICE,
        "style_block": visuals["style_block"],
        "world_block": visuals["world_block"],
        "reference_sheet": {"prompt": visuals["reference_sheet_prompt"], "seed": REFERENCE_SEED},
        "music": {"caption": music["caption"], "bpm": music["bpm"], "key": music["key"],
                  "seeds": SCORE_SEEDS, "cues": music["cues"]},
        "end_card": END_CARD,
        "shots": shots,
    }


def run(film_slug: str, replace: bool = False, refresh: bool = False) -> int:
    film = paths.film(film_slug)
    set_film(film.slug)
    try:
        brief = load_brief(film.brief)  # audience and feeling are required from here on
    except ValidationError as err:
        print(err, file=sys.stderr)
        return 1
    facts_path = film.research / "facts.json"
    if not facts_path.exists():
        print(f"story: no facts yet. Run make research FILM={film.slug} first.", file=sys.stderr)
        return 1
    facts = load_json(facts_path)["facts"]
    subject = load_json(film.research / "subject.json")
    policy = subject.get("likeness_policy", "review")
    cache = Cache(film, STAGE)

    fact_lines = "\n".join(f"{f['id']}: {f['text']}" for f in facts)
    script = ask(
        film, cache, "screenwriter", f"{_intent(brief)}\n\nFacts:\n{fact_lines}", SCRIPT_SCHEMA,
        lambda reply: script_problems(reply, {f["id"] for f in facts}), refresh,
    )

    lines = [shot["narration"] for shot in script["shots"]]
    shot_lines = "\n".join(
        f"Shot {n}. {shot['beat']}. Narration: {shot['narration']}" for n, shot in enumerate(script["shots"], start=1)
    )
    visuals = ask(
        film, cache, "storyboard_artist",
        f"{_intent(brief)}\nWhat the subject is: {subject.get('description') or 'not known'}\n"
        f"How the subject may be shown: {policy}. {subject.get('policy_reason', '')}\n\n"
        f"Facts about the place, the people and the time:\n{fact_lines}\n\nShots:\n{shot_lines}",
        VISUALS_SCHEMA,
        lambda reply: visuals_problems(reply, len(lines), subject_name(brief), policy), refresh,
    )

    starts, clock = [], 0.0
    for line in lines:
        starts.append(clock)
        clock += shot_duration_s(line)
    film_s = clock + END_CARD["duration_s"]
    timed = "\n".join(f"{start:g} s: {shot['beat']}" for start, shot in zip(starts, script["shots"]))
    music = ask(
        film, cache, "composer", f"{_intent(brief)}\nFilm length: {film_s:g} seconds\n\nShots:\n{timed}",
        MUSIC_SCHEMA, lambda reply: music_problems(reply, starts, film_s), refresh,
    )

    translations = {}
    for language in brief["languages"]:
        if language == "en":
            continue
        name = LANGUAGE_NAMES.get(language, language)
        numbered = "\n".join(f"{n}. {line}" for n, line in enumerate(lines, start=1))
        reply = ask(
            film, cache, "translator", f"Target language: {name} (code {language})\n\nEnglish lines:\n{numbered}",
            LINES_SCHEMA, lambda r, language=language: translation_problems(r, lines, language), refresh,
            save_as=f"translator_{language}",
        )
        translations[language] = reply["lines"]

    board = assemble(brief, script, visuals, music, translations)
    draft_path = film.dir / "storyboard.draft.json"
    write_json(draft_path, board)
    try:
        load_storyboard(draft_path)
    except ValidationError as err:
        print(err, file=sys.stderr)
        return 1

    if translations:
        print(f"story: shot lengths are estimates from the English lines. After the voice is recorded, "
              f"run the narration stage with --fit to set them from the {LANGUAGE_NAMES.get(brief['languages'][0], 'spoken')} audio.")
    words = sum(len(line.split()) for line in lines)
    print(f"story: draft has {len(lines)} shots, {words} words, {film_s:g} s. Saved to {film.slug}/storyboard.draft.json.")
    if film.storyboard.exists() and not replace:
        print(f"story: {film.slug}/storyboard.json is the director's and was left alone. "
              "Copy what you want from the draft, or run again with --replace to take all of it.")
    else:
        write_json(film.storyboard, board)
        print(f"story: wrote {film.slug}/storyboard.json. It is now yours to direct: edit it, then approve it.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--film", required=True, help="the film's folder name under films/")
    parser.add_argument("--replace", action="store_true", help="overwrite storyboard.json with the new draft")
    parser.add_argument("--refresh", action="store_true", help="ask the agents again even if nothing changed")
    args = parser.parse_args()
    return run(args.film, args.replace, args.refresh)


if __name__ == "__main__":
    sys.exit(main())
