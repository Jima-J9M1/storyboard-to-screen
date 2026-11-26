"""Edit stage: cut the film together and export it tall (9:16) and wide (16:9).

Reads   films/<slug>/storyboard.json
        outputs/shots/<shot>.<shape>.mp4, outputs/narration/<shot>.<lang>.wav, outputs/music/
Writes  films/<slug>/outputs/film/film_9x16.mp4 and film_16x9.mp4
        films/<slug>/outputs/film/report.json   measured length, loudness, subtitles, music used

In order, from the storyboard:
  1. the shots are joined in order, each starting where the storyboard says, with a short
     dissolve from one into the next;
  2. the end card saying the film was made with AI is added;
  3. each narration line starts with its shot;
  4. the score is lowered under the voice (side-chain ducking) and faded out;
  5. English subtitles are drawn in code and laid over the picture, two lines at most;
  6. the sound is brought to -14 LUFS in two passes, with the peak held under -1 dB.

If no score has been chosen yet, a quiet placeholder chord is used and the report says so:
a film with placeholder music is a rough cut, not the final film.

Nothing here calls a model. The film is rebuilt only when one of its inputs changes.

Usage:
    python -m pipeline.assemble --film gebisa-ejeta
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

from core import audio, motion, paths, titles
from core.cache import Cache
from core.contracts import ValidationError, film_duration_s, load_brief, load_storyboard
from core.files import write_json
from core.runlog import input_hash

STAGE = "assembly"
FPS = 25
VOICE_LEAD_S = 0.1  # a line starts this long after its shot does
DISSOLVE_S = 0.4    # each shot blends into the next over this long; the clips are made that much longer for it
# shape: frame, subtitle font size, characters per line, share of the height kept clear below the text
LAYOUT = {
    "9x16": {"frame": (1080, 1920), "font_px": 50, "chars": 30, "bottom_margin": 0.20, "end_font_px": 64},
    "16x9": {"frame": (1920, 1080), "font_px": 46, "chars": 42, "bottom_margin": 0.09, "end_font_px": 64},
}
TARGET_LUFS, TARGET_PEAK_DB = -14, -1.5
PLACEHOLDER = (
    "aevalsrc='0.20*sin(2*PI*196*t)+0.14*sin(2*PI*293.66*t)+0.10*sin(2*PI*392*t)':s=48000:d={d},"
    "tremolo=f=0.15:d=0.5,lowpass=f=900"
)
# Ducking uses the settings the brief gives as a starting point.
DUCK = "sidechaincompress=threshold=0.02:ratio=6:attack=300:release=1500"


def ffmpeg(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["ffmpeg", "-y", "-hide_banner", *args], check=True, capture_output=True, text=True)


def _fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def find_score(film: paths.Film, board: dict) -> Path | None:
    """The score the director chose, if the music stage has made it."""
    seed = board["music"].get("chosen_seed")
    if seed is None:
        return None
    path = film.outputs / "music" / f"candidate_{seed}.m4a"
    return path if path.exists() else None


def loudness(path: Path) -> dict:
    """Measure a file the way a platform would: integrated loudness and true peak."""
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-af",
         f"loudnorm=I={TARGET_LUFS}:TP={TARGET_PEAK_DB}:LRA=11:print_format=json", "-f", "null", "-"],
        check=True, capture_output=True, text=True,
    )
    return json.loads(re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", result.stderr).group(0))


def build_sound(film: paths.Film, board: dict, work: Path, total_s: float,
                score: Path | None = None) -> tuple[Path, Path | None]:
    """Voice over ducked music, loudness-normalised in two passes. Returns (sound file, score used).

    score  a particular score to mix in; without it, the one the director chose (or the placeholder)
    """
    language = board["languages"][0]
    clips, start = [], 0.0
    for shot in board["shots"]:
        line = film.outputs / "narration" / f"{shot['id']}.{language}.wav"
        if shot["narration"][language].strip():
            clips.append((start + VOICE_LEAD_S, line))
        start += shot["duration_s"]
    voice = work / "voice.wav"
    audio.write_pcm(voice, audio.lay_out(clips, total_s))

    score = score or find_score(film, board)
    music_in = ["-stream_loop", "-1", "-i", str(score)] if score else ["-f", "lavfi", "-i", PLACEHOLDER.format(d=total_s)]
    mix = work / "mix.wav"
    graph = (
        "[0:a]aresample=48000,asplit=2[voice][key];"
        f"[1:a]aresample=48000,volume=0.5,afade=t=in:d=1.5,afade=t=out:st={total_s - 2.5}:d=2.5[music];"
        f"[music][key]{DUCK}[bed];"
        "[voice][bed]amix=inputs=2:normalize=0:duration=first[mix]"
    )
    ffmpeg("-loglevel", "error", "-i", str(voice), *music_in, "-filter_complex", graph,
           "-map", "[mix]", "-t", str(total_s), "-ac", "2", str(mix))

    measured = loudness(mix)   # pass 1: measure; pass 2: apply exactly the gain that is needed
    sound = work / "sound.wav"
    ffmpeg("-loglevel", "error", "-i", str(mix), "-af",
           f"loudnorm=I={TARGET_LUFS}:TP={TARGET_PEAK_DB}:LRA=11:measured_I={measured['input_i']}:"
           f"measured_TP={measured['input_tp']}:measured_LRA={measured['input_lra']}:"
           f"measured_thresh={measured['input_thresh']}:offset={measured['target_offset']}:linear=true,"
           "alimiter=limit=0.84:level=disabled", "-ar", "48000", "-ac", "2", str(sound))
    return sound, score


def subtitle_plan(film: paths.Film, board: dict, shape: str, work: Path) -> list[dict]:
    """Draw every subtitle card for one shape and say when each is on screen."""
    layout, language = LAYOUT[shape], board["languages"][0]
    plan, start = [], 0.0
    for shot in board["shots"]:
        text = shot["subtitle_en"].strip()
        if text:
            spoken = audio.duration_s(film.outputs / "narration" / f"{shot['id']}.{language}.wav")
            cards = titles.subtitle_cards(text, layout["chars"])
            for n, (card, (on, off)) in enumerate(zip(cards, titles.card_times(cards, start + VOICE_LEAD_S, spoken))):
                image = work / f"sub_{shape}_{shot['id']}_{n}.png"
                titles.draw_subtitle(card, image, frame=layout["frame"], font_px=layout["font_px"],
                                     bottom_margin=layout["bottom_margin"])
                plan.append({"shot": shot["id"], "text": card, "on_s": on, "off_s": off, "image": image})
        start += shot["duration_s"]
    return plan


def build_film(film: paths.Film, board: dict, shape: str, sound: Path, work: Path, out: Path) -> list[dict]:
    layout = LAYOUT[shape]
    end_s = board["end_card"]["duration_s"]
    end_image = work / f"end_{shape}.png"
    titles.draw_end_card(board["end_card"]["text"], end_image, frame=layout["frame"], font_px=layout["end_font_px"])
    plan = subtitle_plan(film, board, shape, work)

    inputs: list[str] = []
    for shot in board["shots"]:
        inputs += ["-i", str(film.outputs / "shots" / f"{shot['id']}.{shape}.mp4")]
    inputs += ["-loop", "1", "-framerate", str(FPS), "-t", str(end_s + DISSOLVE_S), "-i", str(end_image)]
    for card in plan:
        inputs += ["-i", str(card["image"])]
    inputs += ["-i", str(sound)]

    shots = len(board["shots"])
    # Every input gets the same frame rate, time base and pixel format, which a dissolve needs.
    graph = "".join(f"[{n}:v]fps={FPS},format=yuv420p,setsar=1,settb=AVTB[c{n}];" for n in range(shots + 1))
    # Shot n+1 starts fading in exactly where shot n+1 begins in the storyboard, over the extra
    # frames at the end of shot n. The narration's timing is untouched.
    start, joined = 0.0, "c0"
    for n, shot in enumerate(board["shots"], start=1):
        start += shot["duration_s"]
        graph += f"[{joined}][c{n}]xfade=transition=fade:duration={DISSOLVE_S}:offset={start:.3f}[x{n}];"
        joined = f"x{n}"
    graph += f"[{joined}]null[v0];"
    for n, card in enumerate(plan):
        graph += (f"[v{n}][{shots + 1 + n}:v]overlay=0:0:"
                  f"enable='between(t,{card['on_s']},{card['off_s']})'[v{n + 1}];")
    graph = graph.rstrip(";")

    out.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg("-loglevel", "error", *inputs, "-filter_complex", graph,
           "-map", f"[v{len(plan)}]", "-map", f"{shots + 1 + len(plan)}:a",
           "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-t", str(film_duration_s(board)), str(out))
    return plan


def probe_duration(path: Path) -> float:
    result = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                            check=True, capture_output=True, text=True)
    return round(float(result.stdout.strip()), 2)


def run(film_slug: str) -> int:
    film = paths.film(film_slug)
    try:
        load_brief(film.brief)
        board = load_storyboard(film.storyboard)
    except ValidationError as err:
        print(err, file=sys.stderr)
        return 1

    language = board["languages"][0]
    needed = [film.outputs / "shots" / f"{s['id']}.{shape}.mp4" for s in board["shots"] for shape in LAYOUT]
    needed += [film.outputs / "narration" / f"{s['id']}.{language}.wav" for s in board["shots"] if s["narration"][language].strip()]
    missing = [p.name for p in needed if not p.exists()]
    if missing:
        print(f"assemble: missing {', '.join(missing[:6])}{' ...' if len(missing) > 6 else ''}. "
              f"Run the earlier stages first (make film FILM={film.slug}).", file=sys.stderr)
        return 1

    out_dir, work = film.outputs / "film", film.outputs / "film" / "work"
    outputs = {shape: out_dir / f"film_{shape}.mp4" for shape in LAYOUT}
    report_path = out_dir / "report.json"
    total_s = film_duration_s(board)
    score = find_score(film, board)
    key = input_hash(
        [_fingerprint(p) for p in needed], _fingerprint(score) if score else PLACEHOLDER,
        [(s["id"], s["duration_s"], s["subtitle_en"]) for s in board["shots"]], board["end_card"],
        LAYOUT, TARGET_LUFS, TARGET_PEAK_DB, DUCK, VOICE_LEAD_S, "crf24", "motion-report", DISSOLVE_S,
    )
    cache = Cache(film, STAGE)
    if cache.fresh("film", key):
        print("assemble: the film is up to date; nothing rebuilt.")
        return 0

    work.mkdir(parents=True, exist_ok=True)
    try:
        sound, score = build_sound(film, board, work, total_s)
        plans = {shape: build_film(film, board, shape, sound, work, out) for shape, out in outputs.items()}
        measured = {shape: loudness(out) for shape, out in outputs.items()}
    except subprocess.CalledProcessError as err:
        print(f"assemble: FFmpeg failed:\n{err.stderr[-1500:]}", file=sys.stderr)
        return 1

    report = {
        "planned_s": total_s,
        "end_card": board["end_card"],
        "music": score.name if score else "placeholder chord (no score chosen yet)",
        "placeholder_music": score is None,
        "films": {
            shape: {
                "file": out.name,
                "frame": list(LAYOUT[shape]["frame"]),
                "duration_s": probe_duration(out),
                "loudness_lufs": float(measured[shape]["input_i"]),
                "true_peak_db": float(measured[shape]["input_tp"]),
                "subtitle_cards": len(plans[shape]),
                "longest_subtitle_line": max(len(line) for c in plans[shape] for line in c["text"].split("\n")),
            }
            for shape, out in outputs.items()
        },
        # Where the picture moves and where it stands still, measured from the film itself.
        "motion_9x16": motion.shot_motion(outputs["9x16"], [(s["id"], s["duration_s"]) for s in board["shots"]]),
        "subtitles_9x16": [{k: c[k] for k in ("shot", "on_s", "off_s", "text")} for c in plans["9x16"]],
    }
    write_json(report_path, report)
    cache.store("film", key, [*outputs.values(), report_path])

    for shape, facts in report["films"].items():
        print(f"assemble: {facts['file']}  {facts['duration_s']} s, {facts['loudness_lufs']} LUFS, "
              f"peak {facts['true_peak_db']} dB, {facts['subtitle_cards']} subtitle cards.")
    still = sum(shot["still_s"] for shot in report["motion_9x16"])
    freeze = max(shot["longest_freeze_s"] for shot in report["motion_9x16"])
    print(f"assemble: the picture stands still for {still:.1f} s of the film; the longest freeze is {freeze:.1f} s.")
    if score is None:
        print("assemble: this is a rough cut. The music is a placeholder chord until a score is chosen.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--film", required=True, help="the film's folder name under films/")
    return run(parser.parse_args().film)


if __name__ == "__main__":
    sys.exit(main())
