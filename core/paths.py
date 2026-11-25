"""Where everything lives. Other modules read these at call time, so tests can redirect them.

The repo holds many films. Each film is a folder under films/ with its own brief,
storyboard, research, outputs and cache. The run log is shared: one file for the whole repo.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCHEMA_DIR = ROOT / "schema"
RUNS_PATH = ROOT / "runs.jsonl"
FILMS_DIR = ROOT / "films"

SLUG = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


@dataclass(frozen=True)
class Film:
    """The files of one film. Paths are worked out when asked for, not when the film is named."""

    slug: str

    @property
    def dir(self) -> Path:
        return FILMS_DIR / self.slug

    @property
    def brief(self) -> Path:
        return self.dir / "brief.json"

    @property
    def storyboard(self) -> Path:
        return self.dir / "storyboard.json"

    @property
    def research(self) -> Path:
        return self.dir / "research"

    @property
    def outputs(self) -> Path:
        return self.dir / "outputs"

    @property
    def cache(self) -> Path:
        return self.dir / "cache"


def film(slug: str) -> Film:
    """Name a film. The slug is checked so it can never point outside films/."""
    if not SLUG.match(slug or ""):
        raise SystemExit(
            f"\"{slug}\" is not a film name. Use lower-case letters, digits and hyphens, "
            "for example gebisa-ejeta."
        )
    return Film(slug)


def film_slugs() -> list[str]:
    """Every film in the repo: each folder under films/ that has a brief."""
    if not FILMS_DIR.is_dir():
        return []
    return sorted(p.name for p in FILMS_DIR.iterdir() if (p / "brief.json").exists() and SLUG.match(p.name))
