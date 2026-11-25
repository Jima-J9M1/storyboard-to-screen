"""Start a new film, or list the films in the repo.

A film starts as a brief: a title, and the audience and feeling the director decides.
Everything else is made from that by the agents and the stages.

Usage:
    python -m core.films new --title "Lalibela"
    python -m core.films new --title "Lalibela" --audience "..." --feeling "..." --languages en am
    python -m core.films list
"""

from __future__ import annotations

import argparse
import sys

from core import paths
from core.contracts import validate_brief
from core.files import slugify, write_json


class FilmExists(Exception):
    pass


def create(title: str, audience: str = "", feeling: str = "", languages: list[str] | None = None,
           sources: list[str] | None = None) -> str:
    """Create films/<slug>/brief.json and return the slug. Audience and feeling may be filled in later."""
    title = " ".join(title.split())
    slug = slugify(title)
    film = paths.film(slug)
    if film.brief.exists():
        raise FilmExists(f"A film named \"{slug}\" already exists.")
    brief = {
        "title": title,
        "audience": audience.strip(),
        "feeling": feeling.strip(),
        "languages": languages or ["en"],
    }
    if sources:
        brief["sources"] = sources
    validate_brief(brief, name="brief", require_intent=False)
    write_json(film.brief, brief)
    return slug


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    new = commands.add_parser("new", help="start a new film")
    new.add_argument("--title", required=True)
    new.add_argument("--audience", default="")
    new.add_argument("--feeling", default="")
    new.add_argument("--languages", nargs="+", default=["en"])
    new.add_argument("--sources", nargs="*", default=[])
    commands.add_parser("list", help="list the films in the repo")
    args = parser.parse_args()

    if args.command == "list":
        for slug in paths.film_slugs():
            print(slug)
        return 0

    try:
        slug = create(args.title, args.audience, args.feeling, args.languages, args.sources)
    except Exception as err:
        print(err, file=sys.stderr)
        return 1
    print(slug)
    return 0


if __name__ == "__main__":
    sys.exit(main())
