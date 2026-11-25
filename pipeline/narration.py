"""Voice stage: speak every shot's narration line, one audio file per shot per language.

Reads   films/<slug>/storyboard.json   each shot's narration, and the narrator's voice and style
Writes  films/<slug>/outputs/narration/<shot>.<lang>.wav
        films/<slug>/outputs/narration/timings.json   how long each line really takes

A line is spoken again only when its text, the voice or the style changes. Change one
line in the storyboard and one file is regenerated.

After speaking, the stage checks every file in two ways, because no agent can listen:
- it measures the file and compares it with the shot's duration in the storyboard;
- it has a model write down what the file says and compares that with the line.
A line that does not fit its shot, or a file that says more or less than its line, is
reported. The fix is the director's: change the line, the shot length or the voice style.

A film has one narrator. If the voice models cannot speak a line, the stage stops short and
says which lines are missing; it does not substitute another voice. `--rough` allows the
Mac's built-in voice as a stand-in for a rough cut, and those lines are re-recorded with
the real voice the next time the stage runs without it.

`--fit` lets the narration set the shot lengths, as the film is cut to the voice: it writes
each shot's `duration_s` in storyboard.json as the length of its spoken line plus a short
pause. Nothing else in the storyboard is touched.

Usage:
    python -m pipeline.narration --film gebisa-ejeta
    python -m pipeline.narration --film gebisa-ejeta --fit
    python -m pipeline.narration --film gebisa-ejeta --rough
"""

from __future__ import annotations

import argparse
import math
import re
import sys

from core import audio, paths, tts
from core.cache import Cache
from core.contracts import ValidationError, load_brief, load_storyboard
from core.files import load_json, write_json
from core.runlog import input_hash, set_film

STAGE = "narration"
STYLE_FORMAT = "[style] text"  # part of the cache key: changing how style is given must re-record
TAIL_S = 0.3  # a line should end at least this long before its shot does
PAUSE_S = 0.4  # with --fit, the pause a shot holds after its line ends
EXTRA_WORDS_ALLOWED = 2  # a transcript may differ slightly: "8" for "eight", a split word


def _words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def heard_problem(line: str, heard: str) -> str | None:
    """Say what is wrong if the audio does not match its line; None if it matches well enough."""
    if not heard:
        return "could not be transcribed, so it was not checked"
    said, meant = _words(heard), _words(line)
    if len(said) > len(meant) + EXTRA_WORDS_ALLOWED:
        return f"says {len(said) - len(meant)} more words than its line: \"{heard}\""
    if len(said) < len(meant) - EXTRA_WORDS_ALLOWED:
        return f"says {len(meant) - len(said)} fewer words than its line: \"{heard}\""
    return None


def fit_durations(film: paths.Film, longest: dict[str, float]) -> float:
    """Set each narrated shot's duration to its spoken length plus a pause. Returns the new film length."""
    board = load_json(film.storyboard)
    for shot in board["shots"]:
        if shot["id"] in longest:
            shot["duration_s"] = math.ceil((longest[shot["id"]] + PAUSE_S) * 20) / 20
    write_json(film.storyboard, board)
    return sum(s["duration_s"] for s in board["shots"]) + board["end_card"]["duration_s"]


def run(film_slug: str, rough: bool = False, fit: bool = False) -> int:
    film = paths.film(film_slug)
    set_film(film.slug)
    try:
        load_brief(film.brief)
        board = load_storyboard(film.storyboard, check_length=not fit)
    except ValidationError as err:
        print(err, file=sys.stderr)
        return 1

    out_dir = film.outputs / "narration"
    cache = Cache(film, STAGE)
    voice = board["voice"]
    spoken = reused = 0
    timings, misfits, misheard, unspoken = [], [], [], []
    longest: dict[str, float] = {}   # per shot, its longest line across languages

    for shot in board["shots"]:
        for language in board["languages"]:
            text = shot["narration"][language].strip()
            if not text:
                continue
            item = f"{shot['id']}.{language}"
            out = out_dir / f"{item}.wav"
            key = input_hash(text, voice, tts.VOICE_MODELS, language, STYLE_FORMAT)
            stand_in = cache.entries.get(item, {}).get("model") == tts.LOCAL_VOICE
            if cache.fresh(item, key) and (rough or not stand_in):
                reused += 1
                model, heard = cache.entries[item].get("model"), cache.entries[item].get("heard", "")
            else:
                try:
                    model = tts.speak(text, out, voice=voice["name"], style=voice["style"],
                                      stage=STAGE, item=item, key=key, allow_local=rough)
                except tts.VoiceUnavailable as err:
                    print(f"narration: {err}")
                    unspoken.append(item)
                    continue
                heard = tts.transcribe(out, stage=STAGE, item=f"{item}.check")
                cache.store(item, key, [out])
                cache.entries[item].update(model=model, heard=heard)
                write_json(cache.path, dict(sorted(cache.entries.items())))
                spoken += 1
            mismatch = heard_problem(text, heard)
            if mismatch:
                misheard.append(f"{item}: {mismatch}")

            audio.trim_silence(out)
            seconds = round(audio.duration_s(out), 2)
            longest[shot["id"]] = max(longest.get(shot["id"], 0), seconds)
            if fit:
                shot = shot | {"duration_s": math.ceil((seconds + PAUSE_S) * 20) / 20}
            fits = seconds + TAIL_S <= shot["duration_s"]
            timings.append({"shot": shot["id"], "language": language, "words": len(text.split()),
                            "spoken_s": seconds, "shot_s": shot["duration_s"], "fits": fits,
                            "model": model, "heard": heard, "matches_line": mismatch is None})
            if not fits:
                misfits.append(f"{item}: the line takes {seconds} s but the shot is {shot['duration_s']} s")

    write_json(out_dir / "timings.json", timings)
    if fit and not unspoken:
        film_s = fit_durations(film, longest)
        print(f"narration: shot lengths in storyboard.json now follow the voice. The film is {film_s:g} s.")
    total = sum(t["spoken_s"] for t in timings)
    words = sum(t["words"] for t in timings)
    rate = f"{words / total:.2f} words a second" if total else "no narration"
    print(f"narration: {spoken} line(s) spoken, {reused} reused. {total:.1f} s of speech, {rate}.")
    for problem in misheard + misfits:
        print(f"narration: {problem}")
    if not misheard and timings:
        print("narration: every file was transcribed and says its line.")
    if misfits:
        print("narration: shorten those lines or lengthen those shots in storyboard.json, then run again.")
    voices = sorted({t["model"] for t in timings})
    if tts.LOCAL_VOICE in voices:
        print("narration: some lines use the Mac's stand-in voice. Run again without --rough to re-record them.")
    elif len(voices) > 1:
        print(f"narration: the lines were spoken by {len(voices)} models using the same voice name "
              f"({', '.join(voices)}). Listen for a change in the narrator between shots.")
    if unspoken:
        print(f"narration: {len(unspoken)} line(s) could not be spoken: {', '.join(unspoken)}. "
              "The voice models are over their limit. Run again in a few minutes; finished lines are kept.")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--film", required=True, help="the film's folder name under films/")
    parser.add_argument("--rough", action="store_true", help="allow the Mac's own voice as a stand-in")
    parser.add_argument("--fit", action="store_true", help="set each shot's length in the storyboard from its spoken line")
    args = parser.parse_args()
    return run(args.film, args.rough, args.fit)


if __name__ == "__main__":
    sys.exit(main())
