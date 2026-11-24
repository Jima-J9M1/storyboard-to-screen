"""Where everything lives. Other modules read these at call time, so tests can redirect them."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SCHEMA_DIR = ROOT / "schema"
BRIEF_PATH = ROOT / "brief.json"
STORYBOARD_PATH = ROOT / "storyboard.json"
RUNS_PATH = ROOT / "runs.jsonl"
CACHE_DIR = ROOT / "cache"
RESEARCH_DIR = ROOT / "research"
OUTPUTS_DIR = ROOT / "outputs"
