"""Every word that appears on screen is drawn here, in code. Pictures never contain text.

Subtitles and the end card are drawn as images with Pillow and laid over the film by FFmpeg.
Pillow's built-in font is used, so the result is the same on any machine and no font file
has to be installed or shipped.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

MAX_LINES = 2  # a subtitle card never has more than two lines


def subtitle_cards(text: str, chars_per_line: int) -> list[str]:
    """Split a subtitle into cards of at most two lines each. Lines are joined with a newline."""
    lines = textwrap.wrap(" ".join(text.split()), width=chars_per_line, break_long_words=False)
    return ["\n".join(lines[n:n + MAX_LINES]) for n in range(0, len(lines), MAX_LINES)]


def card_times(cards: list[str], start_s: float, length_s: float) -> list[tuple[float, float]]:
    """Share a line's spoken time between its cards, by how much text each one holds."""
    total = sum(len(card) for card in cards) or 1
    times, clock = [], start_s
    for card in cards:
        share = length_s * len(card) / total
        times.append((round(clock, 3), round(clock + share, 3)))
        clock += share
    return times


def draw_subtitle(text: str, out: Path, *, frame: tuple[int, int], font_px: int, bottom_margin: float) -> None:
    """A transparent image the size of the frame with one subtitle card near the bottom.

    bottom_margin is the share of the frame's height kept clear below the text: the safe
    area that a phone app's buttons and captions cover.
    """
    width, height = frame
    image = Image.new("RGBA", frame, (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=font_px)
    spacing = round(font_px * 0.3)
    left, top, right, bottom = draw.multiline_textbbox((0, 0), text, font=font, spacing=spacing, align="center")
    text_w, text_h = right - left, bottom - top
    x = (width - text_w) / 2 - left
    y = height * (1 - bottom_margin) - text_h - top
    pad = round(font_px * 0.45)
    draw.rounded_rectangle(
        (x + left - pad, y + top - pad, x + right + pad, y + bottom + pad),
        radius=round(font_px * 0.3), fill=(0, 0, 0, 150),
    )
    draw.multiline_text((x, y), text, font=font, fill=(255, 255, 255, 255), spacing=spacing, align="center")
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)


def draw_end_card(text: str, out: Path, *, frame: tuple[int, int], font_px: int) -> None:
    """A full-frame card that says, in plain words, that the film was made with AI."""
    width, height = frame
    image = Image.new("RGB", frame, (18, 24, 20))
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=font_px)
    wrapped = "\n".join(textwrap.wrap(text, width=max(12, int(width * 0.8 / (font_px * 0.55)))))
    spacing = round(font_px * 0.35)
    left, top, right, bottom = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=spacing, align="center")
    draw.multiline_text(((width - (right - left)) / 2 - left, (height - (bottom - top)) / 2 - top),
                        wrapped, font=font, fill=(240, 240, 232), spacing=spacing, align="center")
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out)
