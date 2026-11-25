"""Validation of the two contracts: brief.json and storyboard.json.

Every stage loads its inputs through this module, so nothing runs on a broken contract.
The JSON Schemas in schema/ carry the structural rules; the rules a schema cannot
express (total running time, a narration line per language) are checked here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from core import paths
from core.files import load_json

MIN_FILM_S, MAX_FILM_S = 60, 90
MIN_INTENT_CHARS = 20


class ValidationError(Exception):
    """A brief or storyboard broke the contract. Carries every problem found."""

    def __init__(self, name: str, problems: list[str]):
        self.name = name
        self.problems = problems
        super().__init__(f"{name} is invalid:\n" + "\n".join(f"  - {p}" for p in problems))


def _schema_problems(instance: Any, schema_name: str) -> list[str]:
    validator = Draft202012Validator(load_json(paths.SCHEMA_DIR / schema_name))
    problems = []
    for err in sorted(validator.iter_errors(instance), key=lambda e: [str(p) for p in e.absolute_path]):
        where = "/".join(str(p) for p in err.absolute_path) or "(top level)"
        if err.validator in ("minItems", "maxItems"):
            # The default message prints the whole array; say the count instead.
            limit = "at least" if err.validator == "minItems" else "at most"
            message = f"has {len(err.instance)} items; needs {limit} {err.validator_value}"
        else:
            message = err.message
        problems.append(f"{where}: {message}")
    return problems


def validate_brief(brief: dict, name: str = "brief.json", require_intent: bool = True) -> dict:
    """Check a brief and return it.

    require_intent=False is for creating a film and for research, which a director may do
    before deciding the audience. Every generating stage requires audience and feeling.
    """
    problems = _schema_problems(brief, "brief.schema.json")
    if not problems and require_intent:
        for field in ("audience", "feeling"):
            if len(brief[field].strip()) < MIN_INTENT_CHARS:
                problems.append(
                    f"{field}: must be written by the director before anything is generated "
                    f"(at least {MIN_INTENT_CHARS} characters)"
                )
    if problems:
        raise ValidationError(name, problems)
    return brief


def load_brief(path: Path, require_intent: bool = True) -> dict:
    """Load and validate a film's brief."""
    if not path.exists():
        raise ValidationError(path.name, ["file not found"])
    return validate_brief(load_json(path), path.name, require_intent)


def load_storyboard(path: Path, check_length: bool = True) -> dict:
    """Load and validate a film's storyboard.

    check_length=False is only for the step that sets shot lengths from the narration: it has
    to be able to open a storyboard whose running time is wrong in order to correct it.
    """
    if not path.exists():
        raise ValidationError(path.name, ["file not found"])
    board = load_json(path)
    problems = _schema_problems(board, "storyboard.schema.json")
    if not problems:
        problems = _storyboard_rule_problems(board)
        if not check_length:
            problems = [p for p in problems if "film runs" not in p]
    if problems:
        raise ValidationError(path.name, problems)
    return board


def film_duration_s(board: dict) -> float:
    return sum(s["duration_s"] for s in board["shots"]) + board["end_card"]["duration_s"]


def _storyboard_rule_problems(board: dict) -> list[str]:
    problems = []
    ids = [s["id"] for s in board["shots"]]
    for dup in sorted({i for i in ids if ids.count(i) > 1}):
        problems.append(f"shots: id {dup} is used more than once")

    total = film_duration_s(board)
    if not MIN_FILM_S <= total <= MAX_FILM_S:
        problems.append(
            f"shots: film runs {total:g} s including the end card; it must be {MIN_FILM_S}-{MAX_FILM_S} s"
        )

    for shot in board["shots"]:
        missing = [lang for lang in board["languages"] if lang not in shot["narration"]]
        if missing:
            problems.append(f"shots/{shot['id']}/narration: missing language(s) {', '.join(missing)}")
        spoken = any(text.strip() for text in shot["narration"].values())
        if spoken and not shot["subtitle_en"].strip():
            problems.append(f"shots/{shot['id']}/subtitle_en: narrated shot has no English subtitle")
    return problems
