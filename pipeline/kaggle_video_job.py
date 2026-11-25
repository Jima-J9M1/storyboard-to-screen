"""The job that runs on a Kaggle GPU: turn pictures into moving clips with Wan 2.2 TI2V-5B.

This file is uploaded and run by pipeline/video.py. It is not imported by the pipeline.
The line starting with JOB is replaced with the list of clips to make before upload.
The pictures arrive as a private Kaggle dataset mounted under /kaggle/input.

The model's documentation asks for a 24 GB GPU at 720p. A Kaggle T4 has 15 GB, so this job
works at 480p with 81 frames and never has two large parts of the model on the GPU at once:
  1. the text encoder (about 11 GB) goes on the GPU alone, turns every prompt into numbers,
     and is then deleted;
  2. only then do the video model (about 10 GB) and the decoder go on the GPU.
The video is decoded in tiles. If the GPU still runs out of memory the job makes fewer
frames, and as a last resort moves the video model on and off the GPU layer by layer,
which is slow but needs very little memory. It records where memory ran out each time.

Clips are made in the order given and each is saved as soon as it is done. The job stops
starting new clips when its time budget is nearly spent, so a long list degrades to
"the first few clips" instead of to nothing.

It writes to /kaggle/working:
    <shot>.<shape>.mp4   one per clip made
    job_report.json      settings, time and memory per clip, and any error
"""

import gc
import glob
import json
import os
import subprocess
import sys
import time
import traceback

JOB = {"clips": [], "steps": 25, "frames": 81, "budget_min": 150, "negative": ""}

OUT = "/kaggle/working"
MODEL = "Wan-AI/Wan2.2-TI2V-5B-Diffusers"
SIZES = {"9x16": (480, 832), "16x9": (832, 480)}   # width, height: both divisible by 32
FPS = 24
report = {"job": {k: v for k, v in JOB.items() if k != "clips"}, "asked": len(JOB["clips"]),
          "started": time.time(), "clips": [], "skipped": [], "notes": [], "steps": [], "error": None}


def save_report():
    report["total_seconds"] = round(time.time() - report["started"], 1)
    with open(f"{OUT}/job_report.json", "w") as f:
        json.dump(report, f, indent=2)


def step(name, command):
    started = time.time()
    done = subprocess.run(command, shell=True, capture_output=True, text=True)
    report["steps"].append({"step": name, "seconds": round(time.time() - started, 1), "code": done.returncode,
                            "tail": (done.stdout + done.stderr)[-1200:]})
    if done.returncode != 0:
        raise RuntimeError(f"{name} failed: {(done.stdout + done.stderr)[-800:]}")


try:
    os.environ["CUDA_VISIBLE_DEVICES"] = "0"   # one T4; the second stays idle
    step("gpu", "nvidia-smi --query-gpu=name,memory.total --format=csv,noheader")
    report["gpu"] = report["steps"][-1]["tail"].strip().splitlines()[0]
    report["python"] = sys.version.split()[0]
    step("install", "pip install -q git+https://github.com/huggingface/diffusers transformers accelerate ftfy imageio imageio-ffmpeg")

    import numpy as np
    import torch
    from diffusers import AutoencoderKLWan, WanImageToVideoPipeline
    from diffusers.utils import export_to_video, load_image
    import diffusers
    report["torch"], report["diffusers"] = torch.__version__, diffusers.__version__
    report["inputs"] = sorted(glob.glob("/kaggle/input/**/*.jpg", recursive=True))[:40]

    def gpu_gb():
        return round(torch.cuda.max_memory_allocated() / 1e9, 2)

    def free():
        gc.collect()
        torch.cuda.empty_cache()

    def picture(name):
        found = glob.glob(f"/kaggle/input/**/{name}", recursive=True)
        if not found:
            raise FileNotFoundError(f"{name} is not in the mounted dataset")
        return load_image(found[0])

    dtype = torch.float16   # a T4 has no fast path for bfloat16
    started = time.time()
    vae = AutoencoderKLWan.from_pretrained(MODEL, subfolder="vae", torch_dtype=torch.float32)
    pipe = WanImageToVideoPipeline.from_pretrained(MODEL, vae=vae, torch_dtype=dtype)
    report["notes"].append(f"model loaded to memory in {round(time.time() - started, 1)} s")
    report["parts"] = {name: type(part).__name__ for name, part in pipe.components.items()}

    # 1. Text encoder alone on the GPU: encode every prompt once, then delete it.
    started = time.time()
    torch.cuda.reset_peak_memory_stats()
    pipe.text_encoder.to("cuda")
    encoded = {}
    with torch.no_grad():
        for prompt in sorted({clip["prompt"] for clip in JOB["clips"]}):
            positive, negative = pipe.encode_prompt(
                prompt=prompt, negative_prompt=JOB["negative"], do_classifier_free_guidance=True,
                num_videos_per_prompt=1, device=torch.device("cuda"),
            )
            encoded[prompt] = (positive.cpu(), negative.cpu())
    report["notes"].append(f"{len(encoded)} prompts encoded in {round(time.time() - started, 1)} s, peak {gpu_gb()} GB")
    pipe.text_encoder.to("cpu")
    pipe.text_encoder = None
    free()

    # 2. Only now the video model and the decoder.
    for name in ("enable_tiling", "enable_slicing"):
        try:
            getattr(pipe.vae, name)()    # decode the video in pieces
        except Exception as err:
            report["notes"].append(f"vae.{name} unavailable: {err}"[:200])
    pipe.transformer.to("cuda")
    pipe.vae.to("cuda")
    report["notes"].append(f"video model on the GPU: {round(torch.cuda.memory_allocated() / 1e9, 2)} GB in use")
    layer_by_layer = False

    def generate(clip, frames):
        width, height = SIZES[clip["shape"]]
        image = picture(clip["file"]).resize((width, height))
        positive, negative = encoded[clip["prompt"]]
        torch.cuda.reset_peak_memory_stats()
        with torch.no_grad():
            result = pipe(
                image=image, prompt_embeds=positive.to("cuda", dtype), negative_prompt_embeds=negative.to("cuda", dtype),
                height=height, width=width, num_frames=frames,
                num_inference_steps=JOB["steps"], guidance_scale=5.0,
                generator=torch.Generator(device="cpu").manual_seed(clip["seed"]),
            ).frames[0]
        return result, np.asarray(result, dtype=np.float32)

    frames = JOB["frames"]
    budget_s, last_s = JOB["budget_min"] * 60, 0.0

    for clip in JOB["clips"]:
        name = f"{clip['shot']}.{clip['shape']}"
        if time.time() - report["started"] + last_s * 1.15 > budget_s:
            report["skipped"].append(name)
            continue
        started = time.time()
        entry = {"clip": name, "seed": clip["seed"], "prompt": clip["prompt"], "tries": []}
        made = None
        for _ in range(5):
            try:
                result, video = generate(clip, frames)
            except torch.OutOfMemoryError:
                where = [line.strip() for line in traceback.format_exc().splitlines() if "site-packages/diffusers" in line][-3:]
                entry["tries"].append({"problem": f"out of memory at {frames} frames", "peak_gb": gpu_gb(),
                                       "layer_by_layer": layer_by_layer, "where": where})
                free()
                if frames > 49:
                    frames = 49
                elif not layer_by_layer:
                    # Last resort: the video model visits the GPU one layer at a time.
                    pipe.to("cpu")
                    free()
                    pipe.enable_sequential_cpu_offload()
                    layer_by_layer, frames = True, JOB["frames"]
                elif frames > 33:
                    frames = 33
                else:
                    break
                continue
            if (not np.isfinite(video).all()) or float(video.std()) < 0.02:
                entry["tries"].append({"problem": "blank output", "mean": float(np.nan_to_num(video).mean())})
                break
            made = result
            entry.update(mean=round(float(video.mean()), 3), contrast=round(float(video.std()), 3))
            break
        last_s = time.time() - started
        entry.update(seconds=round(last_s, 1), frames=frames, dtype=str(dtype), layer_by_layer=layer_by_layer,
                     peak_gpu_gb=gpu_gb(), made=made is not None)
        if made is not None:
            export_to_video(made, f"{OUT}/{name}.mp4", fps=FPS)
            entry["file"] = f"{name}.mp4"
        report["clips"].append(entry)
        save_report()
        if made is None and not any(c["made"] for c in report["clips"]):
            raise RuntimeError(f"the first clip could not be made: {entry['tries']}")
except Exception as err:  # the report is the only way the pipeline learns what went wrong
    report["error"] = f"{type(err).__name__}: {err}"
    report["traceback"] = traceback.format_exc()[-3000:]

save_report()
print(json.dumps({"error": report["error"], "made": [c["clip"] for c in report["clips"] if c.get("made")],
                  "skipped": report["skipped"], "total_seconds": report["total_seconds"]}, indent=2))
