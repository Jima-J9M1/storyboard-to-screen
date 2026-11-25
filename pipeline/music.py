"""Music stage: generate score candidates with ACE-Step 1.5 on a Kaggle GPU.

Reads   films/<slug>/storyboard.json   the music caption, tempo, key and one seed per candidate
Writes  films/<slug>/outputs/music/candidate_<seed>.m4a   one per seed
        films/<slug>/outputs/music/audition_<seed>.m4a    each candidate under the narration, as it will sit in the film
        films/<slug>/outputs/music/job_report.json        the GPU job's own record, with timings

The model needs a GPU, so the work is sent to Kaggle: this stage uploads a small job
(pipeline/kaggle_music_job.py), waits for it, and downloads what it made. The whole job is
one logged call whose latency is the time the GPU session ran.

The director listens to the candidates and writes the seed of the one they choose into
storyboard.json as music.chosen_seed. The Edit stage uses that candidate.

The job is sent again only when the caption, tempo, key, seeds or the film's length change.

The job can wait in Kaggle's queue for most of an hour. If this stage is interrupted, or the
download fails, `--collect` fetches the result of the job that already ran, without sending
a new one.

Usage:
    python -m pipeline.music --film gebisa-ejeta
    python -m pipeline.music --film gebisa-ejeta --collect
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from core import audio, env, paths
from core.cache import Cache
from core.contracts import MAX_FILM_S, ValidationError, film_duration_s, load_brief, load_storyboard
from core.files import load_json, write_json
from core.runlog import input_hash, logged_call, set_film
from pipeline import assemble

STAGE = "music"
MODEL = "ace-step-1.5-turbo (Kaggle T4)"
JOB_FILE = Path(__file__).parent / "kaggle_music_job.py"
ACCELERATOR = "NvidiaTeslaT4"
POLL_S = 30
TIMEOUT_S = 150 * 60   # the first job waited 48 minutes in Kaggle's queue before it ran for 9 seconds


def kaggle(*args: str, timeout: float = 300) -> str:
    """Run the Kaggle command-line tool with the token from .env."""
    tool = Path(sys.executable).parent / "kaggle"
    done = subprocess.run([str(tool), *args], capture_output=True, text=True, timeout=timeout,
                          env={**os.environ, "KAGGLE_API_TOKEN": env.require("KAGGLE_API_TOKEN"),
                               "KAGGLE_USERNAME": env.require("KAGGLE_USERNAME")})
    if done.returncode != 0:
        raise RuntimeError(f"kaggle {args[0]} {args[1]} failed: {(done.stdout + done.stderr).strip()[-600:]}")
    return done.stdout + done.stderr


def run_job(film: paths.Film, job: dict, work: Path, collect: bool = False) -> dict:
    """Upload the job, wait for it to finish, download its output. Returns the job's own report.

    collect=True skips the upload and fetches the output of the job already on Kaggle.
    """
    user = env.require("KAGGLE_USERNAME")
    slug = f"heritage-short-music-{film.slug}"[:50]
    if collect:
        return download(film, user, slug, work, "collected")
    kernel = work / "kernel"
    shutil.rmtree(kernel, ignore_errors=True)
    kernel.mkdir(parents=True)
    source = JOB_FILE.read_text(encoding="utf-8")
    source = re.sub(r"^JOB = .*$", f"JOB = {json.dumps(job)!s}", source, count=1, flags=re.MULTILINE)
    (kernel / "job.py").write_text(source, encoding="utf-8")
    write_json(kernel / "kernel-metadata.json", {
        "id": f"{user}/{slug}", "title": slug, "code_file": "job.py", "language": "python",
        "kernel_type": "script", "is_private": True, "enable_gpu": True, "enable_internet": True,
        "dataset_sources": [], "competition_sources": [], "kernel_sources": [],
    })
    print(f"music: sending the job to Kaggle as {user}/{slug} ...")
    # The GPU is named. Pushed with only "GPU on", the first job sat in the queue for 30 minutes.
    kaggle("kernels", "push", "-p", str(kernel), "--accelerator", ACCELERATOR)

    waited, status = 0, ""
    while waited < TIMEOUT_S:
        time.sleep(POLL_S)
        waited += POLL_S
        status = kaggle("kernels", "status", f"{user}/{slug}").lower()
        if "complete" in status or "error" in status or "cancel" in status:
            break
        if waited % 600 == 0:
            print(f"music: still running on Kaggle after {waited // 60} min ...")
    else:
        raise RuntimeError(f"the Kaggle job did not finish within {TIMEOUT_S // 60} minutes")

    return download(film, user, slug, work, status)


def download(film: paths.Film, user: str, slug: str, work: Path, status: str) -> dict:
    """Fetch a finished job's output, trying a few times: the download host sometimes times out."""
    out = work / "download"
    last = None
    for _ in range(3):
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        try:
            kaggle("kernels", "output", f"{user}/{slug}", "-p", str(out), timeout=900)
            break
        except (RuntimeError, subprocess.TimeoutExpired) as err:
            last = err
            time.sleep(20)
    else:
        raise RuntimeError(f"the job ran, but its output could not be downloaded: {str(last)[-200:]} "
                           "Run the stage again with --collect to fetch it without a new job.")
    report_path = out / "job_report.json"
    if not report_path.exists():
        raise RuntimeError(f"the Kaggle job ended ({status.strip()[-80:]}) without a report; see the notebook's log on kaggle.com")
    report = load_json(report_path)
    if report.get("error"):
        # Keep the failed job's own record: it holds the traceback and each step's output.
        write_json(film.outputs / "music" / "job_report_failed.json", report)
        raise RuntimeError(f"the job failed on Kaggle: {report['error'][:500]}")
    if report.get("job") != load_json(work / "job.json"):
        raise RuntimeError("the job on Kaggle was made from a different music brief than the storyboard's; run the stage without --collect")
    return report


def make_auditions(film: paths.Film, board: dict, candidates: list[Path], cache: Cache) -> int:
    """Mix each candidate under the narration exactly as the Edit stage will, so they can be compared in place.

    A score is chosen for how it sits under the voice, not for how it sounds alone.
    """
    language = board["languages"][0]
    lines = [film.outputs / "narration" / f"{s['id']}.{language}.wav" for s in board["shots"] if s["narration"][language].strip()]
    if not all(line.exists() for line in lines):
        return 0
    total_s, work, made = film_duration_s(board), film.outputs / "music" / "work", 0
    for candidate in candidates:
        out = candidate.with_name(candidate.name.replace("candidate_", "audition_"))
        key = input_hash(candidate.stat().st_size, [audio.duration_s(line) for line in lines],
                         [s["duration_s"] for s in board["shots"]], assemble.DUCK, assemble.TARGET_LUFS)
        if cache.fresh(out.stem, key):
            continue
        work.mkdir(parents=True, exist_ok=True)
        sound, _ = assemble.build_sound(film, board, work, total_s, score=candidate)
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(sound), "-c:a", "aac", "-b:a", "192k", str(out)],
                       check=True, capture_output=True)
        cache.store(out.stem, key, [out])
        made += 1
    shutil.rmtree(work, ignore_errors=True)
    return made


def run(film_slug: str, collect: bool = False) -> int:
    film = paths.film(film_slug)
    set_film(film.slug)
    try:
        load_brief(film.brief)
        board = load_storyboard(film.storyboard)
    except ValidationError as err:
        print(err, file=sys.stderr)
        return 1

    music = board["music"]
    job = {"caption": music["caption"], "bpm": music["bpm"], "key": music["key"], "seeds": music["seeds"],
           # Always the longest a film may be, so the score does not have to be remade when the
           # narration is re-timed. The Edit stage fades it out where the film ends.
           "duration_s": MAX_FILM_S}
    out_dir, work = film.outputs / "music", film.outputs / "music" / "work"
    candidates = [out_dir / f"candidate_{seed}.m4a" for seed in music["seeds"]]
    key = input_hash(job, JOB_FILE.read_text(encoding="utf-8"))
    cache = Cache(film, STAGE)
    if cache.fresh("candidates", key):
        print(f"music: {len(candidates)} candidates are up to date; no job sent.")
    else:
        work.mkdir(parents=True, exist_ok=True)
        write_json(work / "job.json", job)
        try:
            report = logged_call(
                lambda: run_job(film, job, work, collect), stage=STAGE, item="candidates", model=MODEL, params=job,
                seed=music["seeds"][0], key=key, attempts=1,
                measure=lambda r: {"gpu_seconds": r.get("total_seconds"), "gpu": r.get("gpu"),
                                   "per_candidate_s": [c["seconds"] for c in r.get("candidates", [])]},
            )
        except RuntimeError as err:
            print(f"music: {err}", file=sys.stderr)
            return 1
        out_dir.mkdir(parents=True, exist_ok=True)
        for path in candidates:
            # The model writes large WAV files. They are stored as AAC, which is a fifth of the size.
            source = work / "download" / path.with_suffix(".wav").name
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(source), "-c:a", "aac", "-b:a", "256k", str(path)],
                           check=True, capture_output=True)
        write_json(out_dir / "job_report.json", report)
        cache.store("candidates", key, [*candidates, out_dir / "job_report.json"])
        shutil.rmtree(work, ignore_errors=True)
        print(f"music: {len(candidates)} candidates made in {report['total_seconds'] / 60:.1f} GPU minutes.")

    auditions = make_auditions(film, board, candidates, cache)
    if auditions:
        print(f"music: {auditions} audition mix(es) made: each candidate under the narration, as it will sit in the film.")

    chosen = music.get("chosen_seed")
    if chosen is None:
        print("music: listen to them in " + f"{film.slug}/outputs/music/, then write the seed you choose into "
              "storyboard.json as \"chosen_seed\" inside \"music\", and note why in DESIGN.md.")
    else:
        print(f"music: the director chose candidate {chosen}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--film", required=True, help="the film's folder name under films/")
    parser.add_argument("--collect", action="store_true", help="fetch the result of the job already on Kaggle; send nothing")
    args = parser.parse_args()
    return run(args.film, args.collect)


if __name__ == "__main__":
    sys.exit(main())
