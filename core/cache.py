"""Skip work whose inputs have not changed.

Each stage keeps a manifest at cache/<stage>.json mapping an item (a shot id, a title)
to the input hash that produced it and the files it wrote. The manifests are committed,
so a clean clone skips work whose outputs are already in the repo.
"""

from __future__ import annotations

from pathlib import Path

from core import paths
from core.files import load_json, write_json


class Cache:
    def __init__(self, stage: str):
        self.path = paths.CACHE_DIR / f"{stage}.json"
        self.entries: dict = load_json(self.path) if self.path.exists() else {}

    def fresh(self, item: str, key: str) -> bool:
        """True when the item was built from these exact inputs and its files still exist."""
        entry = self.entries.get(item)
        if not entry or entry["input_hash"] != key:
            return False
        return all((paths.ROOT / out).exists() for out in entry["outputs"])

    def store(self, item: str, key: str, outputs: list[Path]) -> None:
        self.entries[item] = {
            "input_hash": key,
            "outputs": [Path(o).resolve().relative_to(paths.ROOT.resolve()).as_posix() for o in outputs],
        }
        write_json(self.path, dict(sorted(self.entries.items())))
