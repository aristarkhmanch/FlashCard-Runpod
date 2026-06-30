"""Image generation through a REAL RunPod Flash @Endpoint (for the
'best use of Flash' prize). Used when IMAGE_BACKEND=flash.

Requires Python 3.10-3.13 and `pip install runpod-flash`. Auth via either
`flash login` or the RUNPOD_API_KEY env var (app.py loads it from .env).

The decorated function's body runs ON the remote GPU. The FIRST call provisions
a worker, installs `dependencies`, and downloads the model (slow cold start);
warm calls reuse the same worker (~10s). _PIPE caches the model in the remote
worker process across warm invocations.
"""
from __future__ import annotations

import asyncio
import base64

from runpod_flash import Endpoint, GpuType

_PIPE = None  # cached in the REMOTE worker process across warm calls


@Endpoint(
    name="flashcard-image",
    gpu=[GpuType.NVIDIA_GEFORCE_RTX_4090],
    dependencies=["torch", "diffusers", "transformers", "accelerate", "sentencepiece"],
)
async def _gen(prompt: str) -> dict:
    import io

    import torch
    from diffusers import AutoPipelineForText2Image

    global _PIPE
    if _PIPE is None:
        _PIPE = AutoPipelineForText2Image.from_pretrained(
            "stabilityai/sdxl-turbo", torch_dtype=torch.float16
        ).to("cuda")
    image = _PIPE(
        prompt=prompt, num_inference_steps=2, guidance_scale=0.0, width=1024, height=1024
    ).images[0]
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    return {"png_b64": base64.b64encode(buf.getvalue()).decode()}


def generate_image_flash(prompt: str) -> bytes:
    result = asyncio.run(_gen(prompt))
    return base64.b64decode(result["png_b64"])
