"""Validate brief.json and storyboard.json. Exits non-zero if either breaks the contract.

Usage:
    python -m pipeline.validate                 # brief (with intent) and storyboard
    python -m pipeline.validate --brief-only    # brief only, for use before a storyboard exists
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from core import paths
from core.contracts import ValidationError, film_duration_s, load_brief, load_storyboard


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--brief", type=Path, default=paths.BRIEF_PATH)
    parser.add_argument("--storyboard", type=Path, default=paths.STORYBOARD_PATH)
    parser.add_argument("--brief-only", action="store_true")
    args = parser.parse_args()

    failed = False
    try:
        brief = load_brief(args.brief)
        print(f"ok  {args.brief.name}: \"{brief['title']}\", languages {', '.join(brief['languages'])}")
    except ValidationError as err:
        print(err, file=sys.stderr)
        failed = True

    if not args.brief_only:
        try:
            board = load_storyboard(args.storyboard)
            print(f"ok  {args.storyboard.name}: {len(board['shots'])} shots, {film_duration_s(board):g} s")
        except ValidationError as err:
            print(err, file=sys.stderr)
            failed = True

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
