"""Standalone Flash validation. Run this FIRST (before touching the app) to
prove the Flash @Endpoint really provisions a GPU and returns an image.

    python flash_smoke.py

The first run is slow (cold start: provision + install deps + download model).
Watch the terminal — worker provisioning logs are the 'best use of Flash' money shot.
"""
from dotenv import load_dotenv

load_dotenv()

import time


def main():
    from flash_image import generate_image_flash

    print("Calling Flash @Endpoint on a real RunPod GPU...")
    print("First call is SLOW (provisioning + deps + model download). Be patient.\n")
    t = time.time()
    png = generate_image_flash(
        "a heroic cyber sorcerer, neon purple energy, holographic GPU motifs, trading card art, ultra detailed"
    )
    open("/tmp/flash_smoke.png", "wb").write(png)
    print("\nOK  %d KB in %.0fs  ->  /tmp/flash_smoke.png" % (len(png) // 1024, time.time() - t))


# Guarded so `flash deploy`'s project scan doesn't execute a generation at import.
if __name__ == "__main__":
    main()
