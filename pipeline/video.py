"""Video stage: turn pictures into moving clips with Wan 2.2 on a Kaggle GPU.

Reads   films/<slug>/storyboard.json   the shots whose motion_mode is "video", their motion prompts and seeds
        films/<slug>/outputs/keyframes/<shot>.jpg
Writes  films/<slug>/outputs/video/<shot>.<shape>.mp4   the clip as the model made it (480p, about 3 seconds)
        films/<slug>/outputs/video/job_report.json      the GPU job's record: time and memory per clip

Only shots marked "video" are sent. The Moving shots stage then uses a generated clip where
one exists and a camera move over the picture where it does not, so a shot the model could
not make, or did not reach before its time ran out, still has a clip.

Clips are asked for in storyboard order, tall first and then wide, and the job stops
starting new ones when its time budget is nearly spent.

A clip is asked for again only when its picture, motion prompt or seed changes.

A clip takes about 12.6 minutes on a Tesla T4 (EXPERIMENTS.md, E10), so ten shots in one
shape is a two-hour job. `--shape` sends one shape only, as its own job, so the tall and the
wide clips can be made side by side on two GPUs.

A clip is 3.4 seconds and a shot is 7 to 10, so one clip cannot fill a shot without being
slowed until it looks like slow motion, or frozen on its last frame (EXPERIMENTS.md, E11).
`--part b` makes a second clip for each shot that starts from the last frame of the first
and carries the motion on. The Moving shots stage joins the two.

Usage:
    python -m pipeline.video --film gebisa-ejeta
    python -m pipeline.video --film gebisa-ejeta --shape 9x16   # the tall clips only, as their own job
    python -m pipeline.video --film gebisa-ejeta --shape 9x16 --part b   # the second clip of each shot
    python -m pipeline.video --film gebisa-ejeta --collect      # fetch a job that already ran
"""

from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path

from core import kaggle, paths
from core.cache import Cache
from core.contracts import ValidationError, load_brief, load_storyboard
from core.files import load_json, write_json
from core.runlog import input_hash, logged_call, set_film

STAGE = "video"
MODEL = "wan-2.2-ti2v-5b (Kaggle T4)"
JOB_FILE = Path(__file__).parent / "kaggle_video_job.py"
SIZES = {"9x16": (480, 832), "16x9": (832, 480)}   # width, height the model works at
SETTINGS = {
    "steps": 25, "frames": 81, "budget_min": 180,
    "negative": "text, letters, watermark, logo, distorted hands, extra fingers, extra limbs, "
                "morphing, flicker, blurry, jerky fast motion, camera shake",
}


def prepare_input(picture: Path, shape: str, out: Path) -> None:
    """Cut the middle of the square picture to the clip's shape, at the size the model works at."""
    width, height = SIZES[shape]
    crop = f"crop=ih*{width}/{height}:ih" if width < height else f"crop=iw:iw*{height}/{width}"
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(picture),
                    "-vf", f"{crop},scale={width}:{height}:flags=lanczos", "-q:v", "2", str(out)],
                   check=True, capture_output=True)


def clip_key(shot: dict, shape: str, picture: Path) -> str:
    """What a generated clip was made from. If the picture, the motion or the seed changes, the clip is stale."""
    return input_hash(hashlib.sha256(picture.read_bytes()).hexdigest()[:16], shot["motion_prompt"],
                      shot["seed"], shape, SIZES[shape], SETTINGS["steps"], SETTINGS["frames"])


def continuation_key(first_key: str, first_clip: Path) -> str:
    """What a shot's second clip was made from: the first clip itself, since it starts from its last frame."""
    return input_hash(first_key, "b", hashlib.sha256(first_clip.read_bytes()).hexdigest()[:16])


def last_frame(clip: Path, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-sseof", "-0.2", "-i", str(clip),
                    "-update", "1", "-frames:v", "1", "-q:v", "2", str(out)], check=True, capture_output=True)


def run(film_slug: str, collect: bool = False, shape: str | None = None, part: str = "a") -> int:
    film = paths.film(film_slug)
    set_film(film.slug)
    try:
        load_brief(film.brief)
        board = load_storyboard(film.storyboard)
    except ValidationError as err:
        print(err, file=sys.stderr)
        return 1

    tag = (f"-{shape}" if shape else "") + ("-b" if part == "b" else "")
    out_dir, work = film.outputs / "video", film.outputs / "video" / f"work{tag}"
    cache = Cache(film, STAGE)
    wanted = [shot for shot in board["shots"] if shot["motion_mode"] == "video"]
    if not wanted:
        print("video: no shot in the storyboard has motion_mode \"video\"; nothing to do.")
        return 0

    # Tall clips for every shot first, then wide: if time runs out, the phone film is complete.
    clips, keys = [], {}
    for clip_shape in ([shape] if shape else list(SIZES)):
        for shot in wanted:
            picture = film.outputs / "keyframes" / f"{shot['id']}.jpg"
            if not picture.exists():
                print(f"video: no picture for {shot['id']}. Run make keyframes FILM={film.slug} first.", file=sys.stderr)
                return 1
            name = f"{shot['id']}.{clip_shape}"
            key = clip_key(shot, clip_shape, picture)
            if part == "b":
                first = out_dir / f"{name}.mp4"
                if not (first.exists() and cache.fresh(name, key)):
                    continue   # a second clip needs an up-to-date first clip to start from
                name, key = f"{name}.b", continuation_key(key, first)
                keys[name] = key
                if not cache.fresh(name, key):
                    clips.append({"shot": shot["id"], "shape": clip_shape, "file": f"{name}.jpg", "name": name,
                                  "prompt": shot["motion_prompt"], "seed": shot["seed"] + 1, "from_clip": str(first)})
                continue
            keys[name] = key
            if not cache.fresh(name, key):
                clips.append({"shot": shot["id"], "shape": clip_shape, "file": f"{name}.jpg",
                              "prompt": shot["motion_prompt"], "seed": shot["seed"]})
    if not clips:
        print(f"video: all {len(keys)} clips are up to date; no job sent.")
        return 0

    job = SETTINGS | {"clips": clips}
    slug = f"heritage-short-video-{film.slug}{tag}"[:50]

    def checked(report: dict) -> dict:
        """A job that made no clip is a failed call, and is logged as one."""
        if not any(clip.get("made") for clip in report.get("clips", [])):
            (film.outputs / "video").mkdir(parents=True, exist_ok=True)
            write_json(film.outputs / "video" / "job_report_failed.json", report)
            raise RuntimeError(f"the job made no clips: {(report.get('error') or 'no reason given')[:400]}")
        return report

    def send() -> dict:
        if collect:
            return checked(kaggle.collect(slug, work))
        inputs = work / "inputs"
        shutil.rmtree(inputs, ignore_errors=True)
        for clip in clips:
            if clip.get("from_clip"):
                last_frame(Path(clip.pop("from_clip")), inputs / clip["file"])
            else:
                prepare_input(film.outputs / "keyframes" / f"{clip['shot']}.jpg", clip["shape"], inputs / clip["file"])
        print(f"video: uploading {len(clips)} pictures to Kaggle ...")
        dataset = kaggle.upload_dataset(f"heritage-short-frames-{film.slug}{tag}"[:50], inputs)
        return checked(kaggle.run_job(slug, JOB_FILE, job, work, datasets=[dataset], timeout_s=5 * 3600, label="video"))

    try:
        report = logged_call(
            send, stage=STAGE, item=f"{len(clips)} clips", model=MODEL, seed=clips[0]["seed"],
            params={k: v for k, v in SETTINGS.items()} | {"clips": [c.get("name") or f"{c['shot']}.{c['shape']}" for c in clips]},
            key=input_hash([keys[c.get("name") or f"{c['shot']}.{c['shape']}"] for c in clips]), attempts=1,
            measure=lambda r: {"gpu_seconds": r.get("total_seconds"), "gpu": r.get("gpu"),
                               "per_candidate_s": [c["seconds"] for c in r.get("clips", []) if c.get("made")],
                               "clips_made": [c["clip"] for c in r.get("clips", []) if c.get("made")]},
        )
    except RuntimeError as err:
        print(f"video: {err}", file=sys.stderr)
        return 1

    out_dir.mkdir(parents=True, exist_ok=True)
    made = []
    for entry in report.get("clips", []):
        source = work / "download" / f"{entry['clip']}.mp4"
        if entry.get("made") and source.exists() and entry["clip"] in keys:
            target = out_dir / source.name
            shutil.move(str(source), str(target))
            cache.store(entry["clip"], keys[entry["clip"]], [target])
            made.append(entry["clip"])
    history = load_json(out_dir / "job_reports.json") if (out_dir / "job_reports.json").exists() else []
    write_json(out_dir / "job_reports.json", history + [report])
    write_json(out_dir / f"job_report{tag}.json", report)

    if report.get("error"):
        print(f"video: the job reported an error: {report['error'][:400]}", file=sys.stderr)
    times = [c["seconds"] for c in report.get("clips", []) if c.get("made")]
    if made:
        print(f"video: {len(made)} clip(s) made ({', '.join(made)}), about {sum(times) / len(times) / 60:.1f} minutes each, "
              f"in a {report.get('total_seconds', 0) / 60:.0f}-minute GPU session.")
    asked = [c.get("name") or f"{c['shot']}.{c['shape']}" for c in clips]
    not_made = [name for name in asked if name not in made]
    if not_made:
        print(f"video: not made this time: {', '.join(not_made)}. Those shots keep their camera move. "
              "Run the stage again to ask for them.")
    return 0 if made else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--film", required=True, help="the film's folder name under films/")
    parser.add_argument("--collect", action="store_true", help="fetch the result of the job already on Kaggle; send nothing")
    parser.add_argument("--shape", choices=list(SIZES), help="make one shape only, as its own job")
    parser.add_argument("--part", choices=["a", "b"], default="a",
                        help="b makes each shot's second clip, continuing from the last frame of its first")
    args = parser.parse_args()
    return run(args.film, args.collect, args.shape, args.part)


if __name__ == "__main__":
    sys.exit(main())
