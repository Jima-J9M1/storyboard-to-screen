"""Validate a film's brief and storyboard. Exits non-zero if either breaks the contract.

Usage:
    python -m pipeline.validate --film gebisa-ejeta
    python -m pipeline.validate --film gebisa-ejeta --brief-only   # before a storyboard exists
"""

from __future__ import annotations

import argparse
import sys

from core import paths
from core.contracts import ValidationError, film_duration_s, load_brief, load_storyboard


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--film", required=True, help="the film's folder name under films/")
    parser.add_argument("--brief-only", action="store_true")
    args = parser.parse_args()
    film = paths.film(args.film)

    failed = False
    try:
        brief = load_brief(film.brief)
        print(f"ok  {film.slug}/brief.json: \"{brief['title']}\", languages {', '.join(brief['languages'])}")
    except ValidationError as err:
        print(err, file=sys.stderr)
        failed = True

    if not args.brief_only:
        try:
            board = load_storyboard(film.storyboard)
            print(f"ok  {film.slug}/storyboard.json: {len(board['shots'])} shots, {film_duration_s(board):g} s")
        except ValidationError as err:
            print(err, file=sys.stderr)
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
