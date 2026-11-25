"""Radio cut: the narration over placeholder music on a black screen.

It exists to test the story on real listeners before any picture is made.

Reads   films/<slug>/storyboard.json and outputs/narration/*.wav
Writes  films/<slug>/outputs/radio_cut/radio_cut.mp4   black screen, for players that want video
        films/<slug>/outputs/radio_cut/radio_cut.m4a   audio only, small enough to send in a chat

Each line starts when its shot starts, so the pauses are the ones the film will have.
If a line is longer than its shot, the next line waits for it, and the cut says by how
much it overran: the story can still be tested while the timing is being fixed.
The placeholder music is a quiet held chord made by FFmpeg; no model is called here.
The music is lowered under the voice and the result is brought to -14 LUFS.

Usage:
    python -m pipeline.radio_cut --film gebisa-ejeta
"""

from __future__ import annotations

import argparse
import subprocess
import sys

from core import audio, paths
from core.cache import Cache
from core.contracts import ValidationError, film_duration_s, load_brief, load_storyboard
from core.runlog import input_hash

STAGE = "radio_cut"
GAP_S = 0.4  # the shortest pause left between two lines
# A soft G chord, slowly swelling. It is only there so the listener hears voice-over-music.
PLACEHOLDER = (
    "aevalsrc='0.20*sin(2*PI*196*t)+0.14*sin(2*PI*293.66*t)+0.10*sin(2*PI*392*t)':s=44100:d={d},"
    "tremolo=f=0.15:d=0.5,lowpass=f=900,afade=t=in:d=2,afade=t=out:st={fade}:d=2"
)
# Ducking: the settings the brief suggests as a starting point.
MIX = (
    "[0:a]aresample=44100,asplit=2[voice][key];"
    "[1:a][key]sidechaincompress=threshold=0.02:ratio=6:attack=300:release=1500[bed];"
    "[voice][bed]amix=inputs=2:normalize=0:duration=longest,loudnorm=I=-14:TP=-1.5:LRA=11,"
    "alimiter=limit=0.84:level=disabled[mix]"   # single-pass loudnorm can overshoot; the limiter holds the peak under -1 dB
)


def run(film_slug: str) -> int:
    film = paths.film(film_slug)
    try:
        load_brief(film.brief)
        board = load_storyboard(film.storyboard)
    except ValidationError as err:
        print(err, file=sys.stderr)
        return 1

    language = board["languages"][0]
    narration_dir = film.outputs / "narration"
    clips, start, missing = [], 0.0, []
    for shot in board["shots"]:
        length = shot["duration_s"]
        if shot["narration"][language].strip():
            path = narration_dir / f"{shot['id']}.{language}.wav"
            if path.exists():
                clips.append((start, path))
                length = max(length, audio.duration_s(path) + GAP_S)   # a long line pushes the next one back
            else:
                missing.append((start, path))
        start += length
    total_s = round(start + board["end_card"]["duration_s"], 2)
    if missing:
        names = ", ".join(path.name for _, path in missing)
        print(f"radio cut: no audio for {names}. Run make narration FILM={film.slug} first.", file=sys.stderr)
        return 1

    out_dir = film.outputs / "radio_cut"
    video, sound, voice_track = out_dir / "radio_cut.mp4", out_dir / "radio_cut.m4a", out_dir / "voice.wav"
    planned_s = film_duration_s(board)
    key = input_hash([(s, audio.duration_s(p), p.stat().st_size) for s, p in clips], total_s, PLACEHOLDER, MIX)
    cache = Cache(film, STAGE)
    if cache.fresh("radio_cut", key):
        print("radio cut: up to date; nothing rebuilt.")
        return 0

    audio.write_pcm(voice_track, audio.lay_out(clips, total_s))
    bed = PLACEHOLDER.format(d=total_s, fade=total_s - 2)
    try:
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error",
             "-i", str(voice_track), "-f", "lavfi", "-i", bed,
             "-f", "lavfi", "-i", f"color=c=black:s=540x960:r=25:d={total_s}",
             "-filter_complex", MIX, "-map", "2:v", "-map", "[mix]",
             "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-t", str(total_s), str(video)],
            check=True, capture_output=True, text=True,
        )
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vn", "-c:a", "copy", str(sound)],
                       check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as err:
        print(f"radio cut: FFmpeg failed:\n{err.stderr}", file=sys.stderr)
        return 1

    cache.store("radio_cut", key, [video, sound])
    print(f"radio cut: {total_s:g} s, {len(clips)} lines. Saved to {film.slug}/outputs/radio_cut/ "
          "(radio_cut.m4a to send, radio_cut.mp4 to play).")
    if total_s > planned_s + 0.01:
        print(f"radio cut: the storyboard plans {planned_s:g} s, but the lines as spoken need {total_s:g} s. "
              "The film must be 60-90 s, so the script or the voice style has to change.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--film", required=True, help="the film's folder name under films/")
    return run(parser.parse_args().film)


if __name__ == "__main__":
    sys.exit(main())
