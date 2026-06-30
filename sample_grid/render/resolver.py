"""The media-URL seam (P4/P5 swap point).

``render`` calls ``resolver.url(sample)`` for every populated cell and never
cares *how* the URL is produced. Phase 1 ships only ``RelativeResolver`` (a
relative ``./assets/...`` reference, file://-safe). Phase 4 swaps a Served
resolver; Phase 5 swaps an Inline (base64) resolver — both behind this Protocol,
with zero renderer change.
"""
from __future__ import annotations

from pathlib import PurePosixPath
from typing import Protocol, runtime_checkable

from sample_grid.core.model import Sample
from sample_grid.util.paths import to_posix


@runtime_checkable
class AssetResolver(Protocol):
    """Maps a Sample to the URL the rendered HTML should reference."""

    def url(self, s: Sample) -> str: ...


class RelativeResolver:
    """Relative-asset bundle resolver: ``./<assets_dir>/<relative sample id>``.

    Keyed on the sample's posix-relative ``id`` (``"<prompt>/<file>"``) rather than
    the bare filename so identical basenames across prompt folders never collide
    in the bundle. This mirrors the relative-asset structure Phase 5 freeze emits.
    """

    def __init__(self, assets_dir: str = "assets") -> None:
        self.assets_dir = assets_dir

    def url(self, s: Sample) -> str:
        rel = to_posix(PurePosixPath(self.assets_dir) / s.id)
        return "./" + rel
