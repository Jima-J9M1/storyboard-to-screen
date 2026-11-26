"""Measure where a film moves and where it stands still, without watching it.

The film is sampled five times a second at a small size, and each sample is compared with
the one before. A stretch where nothing changes is a freeze. This is how the pipeline, whose
builder cannot watch video, checks that a shot keeps moving for as long as it is on screen.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

SAMPLES_PER_SECOND = 5
SIZE = (64, 64)
STILL_BELOW = 0.35   # mean change per pixel, out of 255, under which two samples count as the same picture
# Subtitles sit in the lower part of the frame and change on their own. Only the upper part
# is compared, so a subtitle changing over a frozen picture does not count as motion.
COMPARED_ROWS = 38


def frame_changes(video: Path) -> list[float]:
    """How much the picture changes between each pair of samples, as a list over time."""
    width, height = SIZE
    raw = subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-i", str(video), "-an",
         "-vf", f"fps={SAMPLES_PER_SECOND},scale={width}:{height},format=gray", "-f", "rawvideo", "-"],
        check=True, capture_output=True,
    ).stdout
    size, kept = width * height, width * COMPARED_ROWS
    frames = [raw[i:i + kept] for i in range(0, len(raw) - size + 1, size)]
    return [sum(abs(a - b) for a, b in zip(one, two)) / kept for one, two in zip(frames, frames[1:])]


def shot_motion(video: Path, shots: list[tuple[str, float]]) -> list[dict]:
    """For each shot (id, length in seconds, in order): how long it moves and how long it stands still."""
    changes = frame_changes(video)
    report, start = [], 0.0
    for shot_id, length in shots:
        first, last = round(start * SAMPLES_PER_SECOND), round((start + length) * SAMPLES_PER_SECOND) - 1
        window = changes[first:last]
        still = sum(1 for change in window if change < STILL_BELOW) / SAMPLES_PER_SECOND
        # The longest unbroken freeze is what a viewer notices.
        longest = run = 0
        for change in window:
            run = run + 1 if change < STILL_BELOW else 0
            longest = max(longest, run)
        report.append({
            "shot": shot_id, "length_s": length, "still_s": round(still, 1),
            "longest_freeze_s": round(longest / SAMPLES_PER_SECOND, 1),
            "average_change": round(sum(window) / len(window), 2) if window else 0.0,
        })
        start += length
    return report
