"""Run one stage of a film on request, the way the production board asks for it.

The board does not know how a stage is run. It names a stage, and this module runs the
commands that make it, in order, and reports what they printed. Only one stage runs for a
film at a time.

Stages that take hours on a GPU (generated video, the score) are not run from here: they
are started from the terminal, where a closed browser tab cannot orphan them.

Usage:
    python -m core.run_stage --film gebisa-ejeta --stage keyframes
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from core import paths

# stage id -> the commands that make it, in order. Each is (module, extra arguments).
STEPS: dict[str, list[tuple[str, list[str]]]] = {
    "research": [("agents.researcher", [])],
    "script": [("agents.researcher", []), ("agents.story", [])],
    "radio_cut": [("pipeline.narration", ["--fit"]), ("pipeline.radio_cut", [])],
    "keyframes": [("pipeline.keyframes", [])],
    "narration": [("pipeline.narration", ["--fit"])],
    "shots": [("pipeline.shots", [])],
    "assembly": [("pipeline.shots", []), ("pipeline.assemble", [])],
}
RUNNABLE = set(STEPS)


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


def run(film_slug: str, stage: str) -> dict:
    film = paths.film(film_slug)
    if not film.brief.exists():
        return {"ok": False, "lines": [f"There is no film named \"{film_slug}\"."]}
    if stage not in STEPS:
        return {"ok": False, "lines": [f"The {stage} stage is started from the terminal, not from the board."]}

    lock = film.dir / ".running"
    if lock.exists():
        held = lock.read_text(encoding="utf-8").split()
        if held and held[0].isdigit() and _alive(int(held[0])):
            return {"ok": False, "lines": [f"The {held[1] if len(held) > 1 else 'last'} stage is still running for this film. Wait for it to finish."]}
    lock.write_text(f"{os.getpid()} {stage}", encoding="utf-8")
    lines: list[str] = []
    try:
        for module, extra in STEPS[stage]:
            done = subprocess.run([sys.executable, "-m", module, "--film", film.slug, *extra],
                                  cwd=paths.ROOT, capture_output=True, text=True)
            said = [line for line in (done.stdout + done.stderr).splitlines()
                    if line.strip() and "Trying the next" not in line]
            lines += said[-12:]
            if done.returncode != 0:
                return {"ok": False, "lines": lines}
        return {"ok": True, "lines": lines}
    finally:
        lock.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--film", required=True, help="the film's folder name under films/")
    parser.add_argument("--stage", required=True)
    args = parser.parse_args()
    result = run(args.film, args.stage)
    print("@@RESULT@@" + json.dumps(result, ensure_ascii=False))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
