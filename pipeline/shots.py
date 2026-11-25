"""Moving shots stage: turn each picture into a clip, in both shapes of the film.

Reads   films/<slug>/storyboard.json and outputs/keyframes/<shot>.jpg
Writes  films/<slug>/outputs/shots/<shot>.9x16.mp4 and <shot>.16x9.mp4
        films/<slug>/outputs/shots/moves.json   the camera move used for every shot

Each clip is a slow camera move over the shot's picture ("Ken Burns"), made by FFmpeg on
this machine. The move comes from the shot's motion_prompt: push in, pull back, pan or tilt.
The picture is square; the tall and the wide clip are both cut from its middle.

A shot whose motion_mode is "video" uses the clip the Video stage generated for it
(outputs/video/<shot>.<shape>.mp4), if there is one. The model makes about three seconds;
the clip is slowed, up to twice as long, and then holds its last frame to fill the shot.
If no generated clip exists for a shot, it gets the camera move instead and is listed as
a fallback, so the film can always be cut.

A clip is rebuilt only when its picture, its length or its move changes.

Usage:
    python -m pipeline.shots --film gebisa-ejeta
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys

from core import paths
from core.cache import Cache
from core.contracts import ValidationError, load_brief, load_storyboard
from core.files import write_json
from core.runlog import input_hash
from pipeline.video import STAGE as VIDEO_STAGE, clip_key

STAGE = "shots"
FPS = 25
# name: (width, height, the square the picture is enlarged to, crop taken from its middle)
# The picture is enlarged first so the move is smooth: zooming a small image jitters.
SHAPES = {
    "9x16": (1080, 1920, 2160, "crop=1216:2160"),
    "16x9": (1920, 1080, 3840, "crop=3840:2160"),
}
TRAVEL = 0.12  # how far a move goes: 12 % of the frame over the length of the shot

# The moves a motion_prompt can ask for, checked in this order. Each is a zoompan expression
# in which P runs from 0 at the first frame to 1 at the last.
CENTRE_X, CENTRE_Y = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
HOLD = f"{1 + TRAVEL}"
PAN_LEFT = (HOLD, "(iw-iw/zoom)*(1-P)", CENTRE_Y)
PAN_RIGHT = (HOLD, "(iw-iw/zoom)*P", CENTRE_Y)
MOVES = [
    ("pull back", ("pull back", "pull out", "zoom out"), (f"{1 + TRAVEL}-{TRAVEL}*P", CENTRE_X, CENTRE_Y)),
    # The full phrases come first: "pan left to right" also contains the words "pan left".
    ("pan left to right", ("left to right",), PAN_RIGHT),
    ("pan right to left", ("right to left",), PAN_LEFT),
    ("pan right to left", ("pan left",), PAN_LEFT),
    ("pan left to right", ("pan right", "pan"), PAN_RIGHT),
    ("tilt up", ("tilt up",), (HOLD, CENTRE_X, "(ih-ih/zoom)*(1-P)")),
    ("tilt down", ("tilt down",), (HOLD, CENTRE_X, "(ih-ih/zoom)*P")),
    ("push in", ("push in", "zoom in", "push"), (f"1+{TRAVEL}*P", CENTRE_X, CENTRE_Y)),
]
DEFAULT_MOVE = MOVES[-1]
STILL = ("still", (), ("1", "0", "0"))


def choose_move(motion_mode: str, motion_prompt: str) -> tuple[str, tuple[str, str, str]]:
    """Read the camera move out of a motion prompt. An unrecognised prompt gets a gentle push in."""
    if motion_mode == "still":
        return STILL[0], STILL[2]
    wanted = motion_prompt.lower()
    for name, phrases, expressions in MOVES:
        if any(phrase in wanted for phrase in phrases):
            return name, expressions
    return DEFAULT_MOVE[0], DEFAULT_MOVE[2]


def render(picture, out, shape: str, frames: int, expressions: tuple[str, str, str]) -> None:
    width, height, enlarged, crop = SHAPES[shape]
    progress = f"(on/{max(frames - 1, 1)})"
    zoom, x, y = (e.replace("P", progress) for e in expressions)
    graph = (
        f"scale={enlarged}:{enlarged}:flags=lanczos,{crop},"
        f"zoompan=z='{zoom}':x='{x}':y='{y}':d={frames}:s={width}x{height}:fps={FPS},format=yuv420p"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(picture), "-vf", graph,
         "-frames:v", str(frames), "-r", str(FPS), "-c:v", "libx264", "-preset", "medium", "-crf", "18", str(out)],
        check=True, capture_output=True, text=True,
    )


MAX_SLOW = 2.0   # slower than this and generated motion starts to look like a slideshow


def probe_seconds(path) -> float:
    done = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                          check=True, capture_output=True, text=True)
    return float(done.stdout.strip())


def render_generated(clip, out, shape: str, frames: int) -> tuple[float, float]:
    """Fit a generated clip to its shot: slow it, hold the last frame, enlarge it. Returns (slow factor, seconds held)."""
    width, height, _, _ = SHAPES[shape]
    target = frames / FPS
    raw = probe_seconds(clip)
    slow = max(1.0, min(MAX_SLOW, target / raw))
    hold = max(0.0, target - raw * slow)
    graph = (
        f"setpts={slow:.4f}*PTS,"
        f"minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"   # new in-between frames, so slow motion stays smooth
        f"tpad=stop_mode=clone:stop_duration={hold + 0.5:.3f},"
        f"scale={width}:{height}:force_original_aspect_ratio=increase:flags=lanczos,crop={width}:{height},format=yuv420p"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", str(clip), "-vf", graph, "-frames:v", str(frames),
         "-r", str(FPS), "-an", "-c:v", "libx264", "-preset", "medium", "-crf", "18", str(out)],
        check=True, capture_output=True, text=True,
    )
    return slow, hold


def run(film_slug: str) -> int:
    film = paths.film(film_slug)
    try:
        load_brief(film.brief)
        board = load_storyboard(film.storyboard)
    except ValidationError as err:
        print(err, file=sys.stderr)
        return 1

    keyframes, out_dir = film.outputs / "keyframes", film.outputs / "shots"
    cache = Cache(film, STAGE)
    generated_clips = Cache(film, VIDEO_STAGE)
    made = reused = 0
    moves, fallbacks, missing = [], [], []

    for shot in board["shots"]:
        picture = keyframes / f"{shot['id']}.jpg"
        if not picture.exists():
            missing.append(shot["id"])
            continue
        name, expressions = choose_move(shot["motion_mode"], shot["motion_prompt"])
        frames = round(shot["duration_s"] * FPS)
        look = hashlib.sha256(picture.read_bytes()).hexdigest()[:16]
        made_by = {}
        for shape in SHAPES:
            item, out = f"{shot['id']}.{shape}", out_dir / f"{shot['id']}.{shape}.mp4"
            generated = film.outputs / "video" / f"{shot['id']}.{shape}.mp4"
            # A generated clip is used only if it was made from this shot's current picture and motion.
            use_generated = (shot["motion_mode"] == "video" and generated.exists()
                             and generated_clips.fresh(item, clip_key(shot, shape, picture)))
            if use_generated:
                key = input_hash("generated", hashlib.sha256(generated.read_bytes()).hexdigest()[:16],
                                 frames, SHAPES[shape], FPS, MAX_SLOW)
            else:
                key = input_hash(look, frames, expressions, SHAPES[shape], FPS)
            made_by[shape] = "generated video" if use_generated else f"camera move: {name}"
            if cache.fresh(item, key):
                reused += 1
                continue
            try:
                if use_generated:
                    render_generated(generated, out, shape, frames)
                else:
                    render(picture, out, shape, frames, expressions)
            except subprocess.CalledProcessError as err:
                print(f"shots: FFmpeg failed on {item}:\n{err.stderr}", file=sys.stderr)
                return 1
            cache.store(item, key, [out])
            made += 1
        fell_back = shot["motion_mode"] == "video" and any("camera move" in how for how in made_by.values())
        if fell_back:
            fallbacks.append(shot["id"])
        summary = made_by["9x16"] if len(set(made_by.values())) == 1 else f"tall: {made_by['9x16']}; wide: {made_by['16x9']}"
        moves.append({"shot": shot["id"], "asked": shot["motion_prompt"], "mode": shot["motion_mode"],
                      "move": summary, "frames": frames, "fallback": fell_back})

    write_json(out_dir / "moves.json", moves)
    print(f"shots: {made} clip(s) made, {reused} reused, for {len(moves)} shots in {len(SHAPES)} shapes.")
    if fallbacks:
        print(f"shots: {', '.join(fallbacks)} asked for generated video but have no generated clip yet (in one or both shapes); "
              "they use a camera move over the picture there.")
    if missing:
        print(f"shots: no picture for {', '.join(missing)}. Run make keyframes FILM={film.slug} first.", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--film", required=True, help="the film's folder name under films/")
    return run(parser.parse_args().film)


if __name__ == "__main__":
    sys.exit(main())
