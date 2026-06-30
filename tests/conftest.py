"""Shared pytest fixtures for the sample-html-generator suite.

The fixtures here build *real* on-disk sample folders that follow the documented
Phase-1 grouping convention (immediate parent dir = prompt, first integer in the
file stem = step): ``outputs/<prompt>/step_<N>.png``.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

# Documented Phase-1 convention fixture axes.
PROMPTS = ["a serene lake", "a city street"]
STEPS = [200, 600, 1000]

# Tiny, uniform aspect ratio (32x18 ~= 16:9) so the dense happy path has no
# AR mismatch and every cell shares the detected universal aspect ratio.
IMG_W, IMG_H = 32, 18


def _write_png(path: Path, color: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (IMG_W, IMG_H), color).save(path, format="PNG")


@pytest.fixture
def dense_sample_folder(tmp_path: Path) -> Path:
    """A finished output folder where every (prompt, step) coordinate is populated.

    Layout: ``<tmp>/outputs/<prompt>/step_<N>.png`` for the cartesian product of
    PROMPTS x STEPS. Returns the ``outputs`` directory to point ``build`` at.
    """
    outputs = tmp_path / "outputs"
    for pi, prompt in enumerate(PROMPTS):
        for si, step in enumerate(STEPS):
            # Distinct-but-uniform-AR fill so each image is a valid, decodable PNG.
            color = (30 + pi * 40, 60 + si * 30, 90)
            _write_png(outputs / prompt / f"step_{step}.png", color)
    return outputs
