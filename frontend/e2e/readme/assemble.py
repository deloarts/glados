"""Builds the README pictures in docs/assets from the frames readme.spec.ts captured.

The walkthrough frames become one looping animated WebP, scaled down so the file stays small
enough for a README, and the last screen fades back into the first so the loop has no hard cut.
The dashboard screenshots are copied as optimised PNGs for the light and dark hero image.

Usage: python3 assemble.py <capture dir> <docs/assets dir>
It needs Pillow with WebP support.
"""

import json
import sys
from pathlib import Path

from PIL import Image

TOUR_WIDTH = 1200
TOUR_QUALITY = 82
FADE_FRAMES = 8
FADE_MS = 50


def load_tour(frames_dir: Path) -> tuple[list[Image.Image], list[int]]:
    """Reads the walkthrough frames in order with how long each one shows."""
    manifest = json.loads((frames_dir / "manifest.json").read_text())
    frames: list[Image.Image] = []
    durations: list[int] = []
    for entry in manifest:
        with Image.open(frames_dir / entry["file"]) as frame:
            height = round(frame.height * TOUR_WIDTH / frame.width)
            frames.append(frame.convert("RGB").resize((TOUR_WIDTH, height), Image.Resampling.LANCZOS))
        durations.append(int(entry["ms"]))
    return frames, durations


def add_loop_fade(frames: list[Image.Image], durations: list[int]) -> None:
    """Blends the last frame into the first, so the loop restarts without a jump."""
    first, last = frames[0], frames[-1]
    for step in range(1, FADE_FRAMES + 1):
        frames.append(Image.blend(last, first, step / (FADE_FRAMES + 1)))
        durations.append(FADE_MS)


def build_tour(capture_dir: Path, assets_dir: Path) -> Path:
    frames, durations = load_tour(capture_dir / "walkthrough")
    add_loop_fade(frames, durations)
    target = assets_dir / "glados-tour.webp"
    frames[0].save(
        target,
        save_all=True,
        append_images=frames[1:],
        duration=durations,
        loop=0,
        quality=TOUR_QUALITY,
        method=6,
    )
    return target


def build_heroes(capture_dir: Path, assets_dir: Path) -> list[Path]:
    targets: list[Path] = []
    for theme in ("light", "dark"):
        target = assets_dir / f"glados-dashboard-{theme}.png"
        with Image.open(capture_dir / f"dashboard-{theme}.png") as shot:
            shot.convert("RGB").save(target, optimize=True)
        targets.append(target)
    return targets


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    capture_dir, assets_dir = Path(sys.argv[1]), Path(sys.argv[2])
    assets_dir.mkdir(parents=True, exist_ok=True)
    for target in [*build_heroes(capture_dir, assets_dir), build_tour(capture_dir, assets_dir)]:
        print(f"{target}  {target.stat().st_size / 1024:.0f} KiB")


if __name__ == "__main__":
    main()
