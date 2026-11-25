"""Run a job on a Kaggle GPU: upload a script, wait for it, download what it made.

Kaggle gives free GPU time but makes jobs wait in a queue, so everything here is built to
be picked up again: a job that already ran can be collected without sending a new one.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from core import env
from core.files import load_json, write_json

ACCELERATOR = "NvidiaTeslaT4"
POLL_S = 30


def kaggle(*args: str, timeout: float = 300) -> str:
    """Run the Kaggle command-line tool with the token from .env."""
    tool = Path(sys.executable).parent / "kaggle"
    done = subprocess.run([str(tool), *args], capture_output=True, text=True, timeout=timeout,
                          env={**os.environ, "KAGGLE_API_TOKEN": env.require("KAGGLE_API_TOKEN"),
                               "KAGGLE_USERNAME": env.require("KAGGLE_USERNAME")})
    if done.returncode != 0:
        raise RuntimeError(f"kaggle {' '.join(args[:2])} failed: {(done.stdout + done.stderr).strip()[-600:]}")
    return done.stdout + done.stderr


def user() -> str:
    return env.require("KAGGLE_USERNAME")


def upload_dataset(slug: str, folder: Path, timeout_s: int = 900) -> str:
    """Put a folder of files on Kaggle as a private dataset, and wait until jobs can read it.

    Returns the dataset's id, "<user>/<slug>". An existing dataset gets a new version.
    """
    ref = f"{user()}/{slug}"
    write_json(folder / "dataset-metadata.json", {"title": slug, "id": ref, "licenses": [{"name": "other"}]})
    try:
        kaggle("datasets", "status", ref)
        exists = True
    except RuntimeError:
        exists = False
    if exists:
        kaggle("datasets", "version", "-p", str(folder), "-m", "inputs for the next job", timeout=900)
    else:
        kaggle("datasets", "create", "-p", str(folder), timeout=900)
    waited = 0
    while waited < timeout_s:
        time.sleep(15)
        waited += 15
        try:
            if "ready" in kaggle("datasets", "status", ref).lower():
                return ref
        except RuntimeError:
            pass   # a dataset that was just created is not visible for the first few seconds
    raise RuntimeError(f"the dataset {ref} was uploaded but Kaggle did not finish processing it in {timeout_s // 60} minutes")


def run_job(slug: str, job_file: Path, job: dict, work: Path, *, datasets: list[str] | None = None,
            timeout_s: int = 150 * 60, label: str = "job") -> dict:
    """Upload a job script with its settings filled in, wait for it, and return its own report."""
    ref = f"{user()}/{slug}"
    kernel = work / "kernel"
    shutil.rmtree(kernel, ignore_errors=True)
    kernel.mkdir(parents=True)
    source = job_file.read_text(encoding="utf-8")
    source = re.sub(r"^JOB = .*$", lambda _: f"JOB = {json.dumps(job)}", source, count=1, flags=re.MULTILINE)
    (kernel / "job.py").write_text(source, encoding="utf-8")
    write_json(kernel / "kernel-metadata.json", {
        "id": ref, "title": slug, "code_file": "job.py", "language": "python",
        "kernel_type": "script", "is_private": True, "enable_gpu": True, "enable_internet": True,
        "dataset_sources": datasets or [], "competition_sources": [], "kernel_sources": [],
    })
    write_json(work / "job.json", job)
    print(f"{label}: sending the job to Kaggle as {ref} ...")
    kaggle("kernels", "push", "-p", str(kernel), "--accelerator", ACCELERATOR)

    waited, status = 0, ""
    while waited < timeout_s:
        time.sleep(POLL_S)
        waited += POLL_S
        try:
            status = kaggle("kernels", "status", ref).lower()
        except (RuntimeError, subprocess.TimeoutExpired):
            continue   # one failed check is not a failed job
        if "complete" in status or "error" in status or "cancel" in status:
            break
        if waited % 600 == 0:
            print(f"{label}: still on Kaggle after {waited // 60} min ({'queued' if 'queued' in status else 'running'}) ...")
    else:
        raise RuntimeError(f"the Kaggle job did not finish within {timeout_s // 60} minutes; "
                           "collect it later without sending a new one")
    return collect(slug, work)


def collect(slug: str, work: Path) -> dict:
    """Download the output of the job already on Kaggle and return its report.

    The files land in work/download. The download host sometimes times out, so it is tried
    three times. The report is returned even if the job recorded an error: the caller decides.
    """
    ref = f"{user()}/{slug}"
    out, last = work / "download", None
    for _ in range(3):
        shutil.rmtree(out, ignore_errors=True)
        out.mkdir(parents=True)
        try:
            kaggle("kernels", "output", ref, "-p", str(out), timeout=1800)
            break
        except (RuntimeError, subprocess.TimeoutExpired) as err:
            last = err
            time.sleep(20)
    else:
        raise RuntimeError(f"the job ran, but its output could not be downloaded: {str(last)[-200:]} "
                           "Run the stage again with --collect to fetch it without a new job.")
    report_path = out / "job_report.json"
    if not report_path.exists():
        raise RuntimeError(f"the Kaggle job {ref} ended without a report; see its log on kaggle.com")
    return load_json(report_path)
