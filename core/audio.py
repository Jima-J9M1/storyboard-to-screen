"""Small helpers for the 24 kHz mono 16-bit WAV files the pipeline works in."""

from __future__ import annotations

import wave
from pathlib import Path

SAMPLE_RATE = 24000
SAMPLE_BYTES = 2  # 16-bit


def read_pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as wav:
        shape = (wav.getframerate(), wav.getnchannels(), wav.getsampwidth())
        if shape != (SAMPLE_RATE, 1, SAMPLE_BYTES):
            raise ValueError(f"{path.name} is {shape}, expected 24 kHz mono 16-bit")
        return wav.readframes(wav.getnframes())


def duration_s(path: Path) -> float:
    return len(read_pcm(path)) / (SAMPLE_RATE * SAMPLE_BYTES)


def silence(seconds: float) -> bytes:
    return b"\x00" * (int(round(seconds * SAMPLE_RATE)) * SAMPLE_BYTES)


def write_pcm(path: Path, pcm: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(SAMPLE_BYTES)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm)


def lay_out(clips: list[tuple[float, Path]], total_s: float) -> bytes:
    """One track of `total_s` seconds with each clip starting at its time. Clips must not overlap."""
    track = bytearray(silence(total_s))
    for start_s, path in clips:
        pcm = read_pcm(path)
        offset = int(round(start_s * SAMPLE_RATE)) * SAMPLE_BYTES
        if offset + len(pcm) > len(track):
            track.extend(silence((offset + len(pcm) - len(track)) / (SAMPLE_RATE * SAMPLE_BYTES)))
        track[offset:offset + len(pcm)] = pcm
    return bytes(track)


def trim_silence(path: Path, keep_s: float = 0.08, threshold: int = 250) -> float:
    """Cut the quiet lead-in and tail off a clip, leaving a short margin. Returns the seconds removed.

    Voice models pad each line with about a quarter of a second at both ends. Over ten lines
    that is five seconds of film in which nothing is said.
    """
    pcm = read_pcm(path)
    samples = memoryview(pcm).cast("h")
    count = len(samples)
    first = next((i for i in range(count) if abs(samples[i]) > threshold), 0)
    last = next((i for i in range(count - 1, -1, -1) if abs(samples[i]) > threshold), count - 1)
    margin = int(keep_s * SAMPLE_RATE)
    start, end = max(0, first - margin), min(count, last + 1 + margin)
    removed = (count - (end - start)) / SAMPLE_RATE
    if removed > 0.01:
        write_pcm(path, pcm[start * SAMPLE_BYTES:end * SAMPLE_BYTES])
    return removed
