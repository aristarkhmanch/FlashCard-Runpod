"""OPTIONAL: image generation through a RunPod Flash @Endpoint (for the
'best use of Flash' prize narrative). Only used when IMAGE_BACKEND=flash.

Setup once:
    pip install runpod-flash
    flash login
Then set IMAGE_BACKEND=flash in .env and run the app. The FIRST call provisions
a GPU and downloads the model (slow cold start) — pre-warm before the demo with:
    flash dev --auto-provision
"""
from __future__ import annotations

import base64

_PIPE = None  # cached across warm invocations


def generate_image_flash(prompt: str) -> bytes:
    from runpod_flash import Endpoint, GpuType

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
                "stabilityai/sdxl-turbo",
                torch_dtype=torch.float16,
                cache_dir="/runpod-volume/hf",  # cache weights on the network volume
            ).to("cuda")
        image = _PIPE(prompt=prompt, num_inference_steps=4, guidance_scale=0.0,
                      width=1024, height=1024).images[0]
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        return {"png_b64": base64.b64encode(buf.getvalue()).decode()}

    import asyncio
    result = asyncio.run(_gen(prompt))
    return base64.b64decode(result["png_b64"])
