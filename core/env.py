"""API keys. They live in .env, which is never committed."""

from __future__ import annotations

import os

from core import paths


def load_env() -> None:
    """Read KEY=value lines from .env into the environment. Real environment variables win."""
    env_path = paths.ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        value = value.strip().strip("'\"")
        if value:
            os.environ.setdefault(name.strip(), value)


def require(name: str) -> str:
    """Return a key, or stop with an instruction on how to provide it."""
    load_env()
    value = os.environ.get(name, "").strip()
    if not value:
        raise SystemExit(
            f"{name} is not set. Copy .env.example to .env and fill it in. "
            "See the README for where to get each key."
        )
    return value
