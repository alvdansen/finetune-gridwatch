"""Media discovery classification — the video/image allowlist split (Phase 3).

Pairs with ``test_grid.py``'s scanner usage. These focused units pin two things:
  * ``media_type_for`` is the ONE suffix→media_type classifier (single source of
    truth) — ``.mp4``/``.webm`` (any case) → ``"video"``, images → ``"image"``;
  * the Scanner UNION allowlist picks up video beside images, while the DISJOINT
    ``SIDECAR_EXTENSIONS`` keeps ``.json`` out of the media index (Pitfall 6).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from sample_grid.core.scan import Scanner, media_type_for


@pytest.mark.parametrize(
    "name,expected",
    [
        ("clip.mp4", "video"),
        ("clip.webm", "video"),
        ("CLIP.MP4", "video"),   # classification is case-insensitive
        ("pic.png", "image"),
        ("pic.jpg", "image"),
        ("pic.jpeg", "image"),
        ("pic.webp", "image"),
    ],
)
def test_media_type_for(name: str, expected: str) -> None:
    # Accepts both a Path and a plain string path.
    assert media_type_for(Path(name)) == expected
    assert media_type_for(name) == expected


def test_scan_picks_up_video(video_sample_folder: Path) -> None:
    """A ``.mp4`` beside ``.png`` files is discovered by ``Scanner().scan``; a
    ``.json`` sidecar in the same folder is NOT (disjoint allowlist)."""
    found = Scanner().scan(video_sample_folder)
    suffixes = {p.suffix.lower() for p in found}

    # Video is now a first-class media type alongside images.
    assert ".mp4" in suffixes
    assert ".png" in suffixes
    # The disjoint sidecar allowlist keeps the .json OUT of the media index.
    assert ".json" not in suffixes
    assert all(p.suffix.lower() != ".json" for p in found)
