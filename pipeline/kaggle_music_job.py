"""The job that runs on a Kaggle GPU: generate score candidates with ACE-Step 1.5.

This file is uploaded and run by pipeline/music.py. It is not imported by the pipeline.
The line starting with JOB is replaced with the film's music brief before upload.

Kaggle's own Python is newer than ACE-Step supports, so the job does not use it for the
model. It installs `uv`, lets uv build ACE-Step's environment with a Python it supports,
and runs the generation inside that environment.

It writes to /kaggle/working:
    candidate_<seed>.wav   one per seed
    job_report.json        what was asked, how long each part took, and any error
"""

import json
import os
import subprocess
import sys
import time
import traceback

JOB = {"caption": "", "bpm": 72, "key": "C major", "seeds": [1], "duration_s": 90}

OUT = "/kaggle/working"
REPO = "/kaggle/working/ACE-Step-1.5"
report = {"job": JOB, "started": time.time(), "candidates": [], "error": None, "steps": []}

# Runs inside ACE-Step's own environment. It records what it finds as it goes, so that a
# failure still tells the next attempt what the library actually looks like.
GENERATE = r'''
import inspect, json, os, sys, time, traceback
JOB = json.loads(os.environ["HERITAGE_JOB"])
OUT, REPO = os.environ["HERITAGE_OUT"], os.environ["HERITAGE_REPO"]
info = {"python": sys.version.split()[0], "candidates": [], "error": None, "notes": []}
try:
    import torch
    info["torch"] = torch.__version__
    info["cuda"] = torch.cuda.is_available()
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music
    from acestep.llm_inference import LLMHandler
    info["signatures"] = {
        "initialize_service": str(inspect.signature(AceStepHandler.initialize_service)),
        "llm_initialize": str(inspect.signature(LLMHandler.initialize)),
        "generate_music": str(inspect.signature(generate_music)),
    }

    started = time.time()
    dit = AceStepHandler()
    result = dit.initialize_service(project_root=REPO, config_path="acestep-v15-turbo", device="cuda")
    info["notes"].append(f"initialize_service returned: {str(result)[:300]}")
    # The planner model is left unloaded: caption, tempo and key come from the storyboard.
    llm = LLMHandler()
    info["load_seconds"] = round(time.time() - started, 1)

    def make(seed):
        params = GenerationParams(
            caption=JOB["caption"], lyrics="[Instrumental]", instrumental=True,
            bpm=JOB["bpm"], keyscale=JOB["key"], duration=JOB["duration_s"],
            inference_steps=8, shift=3.0, seed=seed, thinking=False,
        )
        config = GenerationConfig(batch_size=1, use_random_seed=False, audio_format="wav")
        return generate_music(dit, llm, params, config, save_dir=f"{OUT}/raw_{seed}")

    for seed in JOB["seeds"]:
        started = time.time()
        result = make(seed)
        if not result.success and not info.get("planner_loaded"):
            # The library may insist on the planner model after all. Load the smallest and retry once.
            info["notes"].append(f"without the planner: {result.error} {result.status_message}"[:400])
            llm.initialize(checkpoint_dir=os.path.join(REPO, "checkpoints"),
                           lm_model_path="acestep-5Hz-lm-0.6B", backend="pt", device="cuda")
            info["planner_loaded"] = True
            result = make(seed)
        if not result.success:
            raise RuntimeError(f"seed {seed}: {result.error} {result.status_message}")
        target = f"{OUT}/candidate_{seed}.wav"
        os.replace(result.audios[0]["path"], target)
        info["candidates"].append({"seed": seed, "file": os.path.basename(target),
                                   "seconds": round(time.time() - started, 1)})
except Exception as err:
    info["error"] = f"{type(err).__name__}: {err}"
    info["traceback"] = traceback.format_exc()[-3000:]
    try:
        info["repo_files"] = sorted(os.listdir(REPO))[:60]
    except OSError:
        pass
with open(f"{OUT}/generate_report.json", "w") as f:
    json.dump(info, f, indent=2)
'''


def step(name, command, env=None):
    """Run a shell command, record how long it took, and stop the job if it fails."""
    started = time.time()
    done = subprocess.run(command, shell=True, capture_output=True, text=True, env=env)
    report["steps"].append({"step": name, "seconds": round(time.time() - started, 1), "code": done.returncode,
                            "tail": (done.stdout + done.stderr)[-1500:]})
    if done.returncode != 0:
        raise RuntimeError(f"{name} failed: {(done.stdout + done.stderr)[-800:]}")


try:
    step("gpu", "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader")
    report["gpu"] = report["steps"][-1]["tail"].strip().splitlines()[0]
    report["kaggle_python"] = sys.version.split()[0]
    step("clone", f"git clone --depth 1 https://github.com/ACE-Step/ACE-Step-1.5.git {REPO}")
    step("uv", "pip install -q uv")
    step("environment", f"cd {REPO} && uv sync")   # uv fetches a Python that ACE-Step supports

    with open(f"{REPO}/heritage_generate.py", "w") as f:
        f.write(GENERATE)
    env = {**os.environ, "CUDA_VISIBLE_DEVICES": "0",   # one T4 is enough; the second stays idle
           "HERITAGE_JOB": json.dumps(JOB), "HERITAGE_OUT": OUT, "HERITAGE_REPO": REPO}
    step("generate", f"cd {REPO} && uv run python heritage_generate.py", env=env)

    with open(f"{OUT}/generate_report.json") as f:
        generated = json.load(f)
    report.update({k: generated.get(k) for k in ("candidates", "load_seconds", "torch", "cuda", "signatures", "notes")})
    report["model_python"] = generated.get("python")
    if generated.get("error"):
        report["traceback"] = generated.get("traceback")
        report["repo_files"] = generated.get("repo_files")
        raise RuntimeError(generated["error"])
except Exception as err:  # the report is the only way the pipeline learns what went wrong
    report["error"] = f"{type(err).__name__}: {err}"
    report.setdefault("traceback", traceback.format_exc()[-3000:])

report["total_seconds"] = round(time.time() - report["started"], 1)
with open(f"{OUT}/job_report.json", "w") as f:
    json.dump(report, f, indent=2)
# Keep the output small: only the candidates and the report are downloaded.
subprocess.run(f"rm -rf {REPO} {OUT}/raw_* {OUT}/generate_report.json", shell=True)
print(json.dumps({k: report.get(k) for k in ("error", "candidates", "total_seconds")}, indent=2))
