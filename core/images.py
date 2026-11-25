"""Picture generation, through FLUX.2 klein 4B on Cloudflare Workers AI.

paint() makes one picture from a prompt and a seed, optionally guided by a reference image
so that every picture in a film shares one look. FLUX.2 klein 4B is the Apache-2.0 model;
the 9B version is non-commercial and is not used.
"""

from __future__ import annotations

import base64
from pathlib import Path

from core import env, http
from core.llm import worth_retrying
from core.runlog import logged_call

MODEL = "@cf/black-forest-labs/flux-2-klein-4b"
RUN_URL = "https://api.cloudflare.com/client/v4/accounts/{account}/ai/run/{model}"
# Pictures are square. The tall (9:16) and wide (16:9) films are both cut from the middle
# of the same square, which is why every prompt asks for a centred subject.
SIZE = 1024


def paint(prompt: str, out: Path, *, seed: int, stage: str, item: str, key: str,
          reference: Path | None = None) -> str:
    """Write one picture to `out` (JPEG) and return the name of the model that made it."""
    account = env.require("CLOUDFLARE_ACCOUNT_ID")
    token = env.require("CLOUDFLARE_API_TOKEN")
    fields = {"prompt": prompt, "width": str(SIZE), "height": str(SIZE), "seed": str(seed)}
    files = {"input_image_0": (reference.name, reference.read_bytes(), "image/jpeg")} if reference else None

    def call() -> int:
        reply = http.post_multipart(
            RUN_URL.format(account=account, model=MODEL), fields, files,
            headers={"Authorization": f"Bearer {token}"},
        )
        if not reply.get("success") or not reply.get("result", {}).get("image"):
            raise RuntimeError(f"no picture in the reply: {str(reply.get('errors'))[:200]}")
        data = base64.b64decode(reply["result"]["image"])
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        return len(data)

    logged_call(
        call, stage=stage, item=item, model=MODEL, seed=seed, key=key, retry_if=worth_retrying,
        params={"prompt": prompt, "width": SIZE, "height": SIZE, "reference": reference.name if reference else None},
        measure=lambda size: {"bytes": size},
    )
    return MODEL
