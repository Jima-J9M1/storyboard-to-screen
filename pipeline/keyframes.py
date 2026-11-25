"""Pictures stage: one still picture per shot, all painted against one reference sheet.

Reads   films/<slug>/storyboard.json   the style block, the reference sheet, each shot's picture and seed
Writes  films/<slug>/outputs/keyframes/reference.jpg   the look of the film, made first
        films/<slug>/outputs/keyframes/<shot>.jpg      one picture per shot
        films/<slug>/outputs/keyframes/contact_sheet.jpg   every picture on one page, for review

The reference sheet is generated first, and the style block is added to every prompt.
A shot whose `use_reference` is true is also painted with the reference sheet as a guide
image. Wide landscapes are not: guided by the sheet they come back as copies of it
(EXPERIMENTS.md, E4), and the style block alone keeps their look in line.

A picture is regenerated only when its own prompt or seed changes, or when the style block
or the reference sheet changes (which, correctly, regenerates all of them). Change one
shot's picture in the storyboard and one picture is remade.

Usage:
    python -m pipeline.keyframes --film gebisa-ejeta
    python -m pipeline.keyframes --film gebisa-ejeta --only s03 s07   # just these shots
"""

from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
from pathlib import Path

from core import images, paths
from core.cache import Cache
from core.contracts import ValidationError, load_brief, load_storyboard
from core.runlog import input_hash, set_film

STAGE = "keyframes"
# Added to every prompt. Generated pictures must never contain writing (rule 9).
NO_TEXT = "No text, letters, numbers, captions, logos or watermarks anywhere in the picture."
# {world} is the storyboard's world block: who the people are and where the story happens.
# Without it the picture model falls back on its own defaults for people, dress and buildings.
# It is given as a rule for what appears, not as a list of things to show: stated as a plain
# description, it put villagers and huts into every picture (EXPERIMENTS.md, E6).
ONLY_WHAT_IS_ASKED = (
    "Show only what is described here: do not add people, buildings or objects that the description does not mention. "
)
WORLD_RULE = "Anything from this list that does appear must look as it says, and nothing from it should be added: {world} "
REFERENCE_FRAME = ("A style reference sheet for a film. {prompt} " + ONLY_WHAT_IS_ASKED + WORLD_RULE
                   + "Style: {style} " + NO_TEXT)
SHOT_FRAME = (
    "{prompt} " + ONLY_WHAT_IS_ASKED + WORLD_RULE
    + "Paint it in the same style, palette, light and brushwork as the reference image, "
    "but as a new scene of its own; do not copy the reference's composition or its contents. "
    "Subject centred in the frame. Style: {style} " + NO_TEXT
)
UNGUIDED_FRAME = ("{prompt} " + ONLY_WHAT_IS_ASKED + WORLD_RULE
                  + "Subject centred in the frame. Style: {style} " + NO_TEXT)


def _fingerprint(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def contact_sheet(pictures: list[Path], out: Path) -> None:
    """Every picture on one page, in shot order, so a reviewer can compare them side by side."""
    columns = 4
    rows = -(-len(pictures) // columns)
    inputs = [arg for picture in pictures for arg in ("-i", str(picture))]
    scaled = "".join(f"[{n}:v]scale=384:384[p{n}];" for n in range(len(pictures)))
    tiles = "".join(f"[p{n}]" for n in range(len(pictures)))
    layout = "|".join(f"{(n % columns) * 384}_{(n // columns) * 384}" for n in range(len(pictures)))
    graph = f"{scaled}{tiles}xstack=inputs={len(pictures)}:layout={layout}:fill=black[sheet]"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *inputs, "-filter_complex", graph, "-map", "[sheet]",
         "-frames:v", "1", "-update", "1", "-s", f"{columns * 384}x{rows * 384}", str(out)],
        check=True, capture_output=True, text=True,
    )


def run(film_slug: str, only: list[str] | None = None) -> int:
    film = paths.film(film_slug)
    set_film(film.slug)
    try:
        load_brief(film.brief)
        board = load_storyboard(film.storyboard)
    except ValidationError as err:
        print(err, file=sys.stderr)
        return 1

    out_dir = film.outputs / "keyframes"
    cache = Cache(film, STAGE)
    style, world = board["style_block"], board["world_block"]
    made = reused = 0

    # 1. The reference sheet: the look everything else is painted against.
    reference = out_dir / "reference.jpg"
    sheet = board["reference_sheet"]
    prompt = REFERENCE_FRAME.format(prompt=sheet["prompt"], style=style, world=world)
    key = input_hash(prompt, sheet["seed"], images.MODEL, images.SIZE)
    if cache.fresh("reference", key):
        reused += 1
    else:
        images.paint(prompt, reference, seed=sheet["seed"], stage=STAGE, item="reference", key=key)
        cache.store("reference", key, [reference])
        made += 1
    look = _fingerprint(reference)

    # 2. One picture per shot, guided by the reference sheet.
    failed = []
    for shot in board["shots"]:
        if only and shot["id"] not in only:
            continue
        out = out_dir / f"{shot['id']}.jpg"
        guided = shot["use_reference"]
        frame = SHOT_FRAME if guided else UNGUIDED_FRAME
        prompt = frame.format(prompt=shot["image_prompt"], style=style, world=world)
        key = (input_hash(prompt, shot["seed"], images.MODEL, images.SIZE, look) if guided
               else input_hash(prompt, shot["seed"], images.MODEL, images.SIZE))
        if cache.fresh(shot["id"], key):
            reused += 1
            continue
        try:
            images.paint(prompt, out, seed=shot["seed"], stage=STAGE, item=shot["id"], key=key,
                         reference=reference if guided else None)
        except RuntimeError as err:
            print(f"keyframes: {shot['id']} failed: {str(err).splitlines()[0][:160]}")
            failed.append(shot["id"])
            continue
        cache.store(shot["id"], key, [out])
        made += 1

    pictures = [reference] + [p for p in (out_dir / f"{s['id']}.jpg" for s in board["shots"]) if p.exists()]
    contact_sheet(pictures, out_dir / "contact_sheet.jpg")
    print(f"keyframes: {made} picture(s) made, {reused} reused. "
          f"Review them on {film.slug}/outputs/keyframes/contact_sheet.jpg (reference first, then shot order).")
    if failed:
        print(f"keyframes: {len(failed)} shot(s) have no picture: {', '.join(failed)}. Run again; finished pictures are kept.")
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--film", required=True, help="the film's folder name under films/")
    parser.add_argument("--only", nargs="+", metavar="SHOT", help="make only these shots, for example s03 s07")
    args = parser.parse_args()
    return run(args.film, args.only)


if __name__ == "__main__":
    sys.exit(main())
