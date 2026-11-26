"""Put the repo on a Hugging Face Space, where the Dockerfile builds and runs it.

Sends exactly what is committed (git archive of HEAD), so nothing private or git-ignored can
leave this machine: no .env, no assignment brief, no private notes. The Space's page header,
which Hugging Face requires at the top of README.md, is added to the copy that is sent and
not to the repo's own README.

Needs HF_TOKEN in .env (a Hugging Face access token with write permission) and
`pip install huggingface_hub`. It sets no secrets: add the keys on the Space's Settings page.

Usage:
    python -m deploy.space                      # creates or updates <you>/storyboard-to-screen
    python -m deploy.space --name another-name
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from core import paths
from core.env import require

HEADER = """---
title: Storyboard to Screen
emoji: 🎬
colorFrom: indigo
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
---

"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--name", default="storyboard-to-screen")
    args = parser.parse_args()

    from huggingface_hub import HfApi   # imported here so the pipeline never depends on it

    if subprocess.run(["git", "status", "--porcelain"], cwd=paths.ROOT, capture_output=True, text=True).stdout.strip():
        print("deploy: there are uncommitted changes. Only committed files are sent; commit first.", file=sys.stderr)
        return 1

    api = HfApi(token=require("HF_TOKEN"))
    repo_id = f"{api.whoami()['name']}/{args.name}"
    api.create_repo(repo_id, repo_type="space", space_sdk="docker", exist_ok=True)

    with tempfile.TemporaryDirectory() as stage:
        archive = Path(stage) / "repo.tar"
        subprocess.run(["git", "archive", "--format=tar", "-o", str(archive), "HEAD"], cwd=paths.ROOT, check=True)
        copy = Path(stage) / "repo"
        with tarfile.open(archive) as tar:
            tar.extractall(copy, filter="data")
        readme = copy / "README.md"
        readme.write_text(HEADER + readme.read_text(encoding="utf-8"), encoding="utf-8")
        api.upload_folder(repo_id=repo_id, repo_type="space", folder_path=str(copy),
                          commit_message="Deploy the committed repo", delete_patterns=["*"])
    print(f"deploy: sent to https://huggingface.co/spaces/{repo_id}. It builds for some minutes before it answers.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
