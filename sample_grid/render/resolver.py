"""The media-URL seam (P4/P5 swap point).

``render`` calls ``resolver.url(sample)`` for every populated cell and never
cares *how* the URL is produced. Phase 1 ships only ``RelativeResolver`` (a
relative ``./assets/...`` reference, file://-safe). Phase 4 swaps a Served
resolver; Phase 5 swaps an Inline (base64) resolver — both behind this Protocol,
with zero renderer change.
"""
from __future__ import annotations

import base64
import mimetypes
from pathlib import PurePosixPath
from typing import Protocol, runtime_checkable
from urllib.parse import quote

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


class ServedResolver:
    """Live-server resolver (P4): maps a Sample to a ``/media/<id>`` URL.

    Keyed on the sample's posix-relative ``id`` EXACTLY like ``RelativeResolver``
    (so ``render`` stays resolver-agnostic — proven by
    ``test_renderer_resolver_agnostic``). The local server mounts the output
    folder under ``/media`` and this resolver points every cell at it.

    ``quote(s.id, safe="/")`` keeps the forward slashes as path separators while
    url-encoding each segment (spaces → ``%20``, etc.), so a prompt folder like
    ``"a lake"`` yields ``/media/a%20lake/...`` — a valid URL the browser can
    request without ambiguity.
    """

    def url(self, s: Sample) -> str:
        return "/media/" + quote(s.id, safe="/")


class InlineResolver:
    """Opt-in single-file resolver (P5): embed each sample as a base64 ``data:`` URI.

    A third sibling behind the SAME ``AssetResolver`` Protocol as
    ``RelativeResolver`` / ``ServedResolver``, so ``render(grid, resolver,
    live=False)`` consumes it with ZERO renderer, template, or JS change (proven
    agnostic by ``test_renderer_resolver_agnostic``).

    Intended for images / tiny grids ONLY — the ``freeze`` CLI guardrail degrades
    to the relative folder bundle for video or oversized totals (CLAUDE.md: iOS
    Safari base64 ``<video>`` is unreliable; ~33% inflation; total page weight is
    the real limit). base64 sidesteps paths entirely, so no Windows backslash can
    ever leak into ``src`` (Pitfall 3), and the ``data:`` URI lands inside an
    autoescaped ``src`` / ``href`` — no ``| safe``, no XSS surface (T-5-05).
    """

    def url(self, s: Sample) -> str:
        mime = mimetypes.guess_type(s.path.name)[0] or "application/octet-stream"
        b64 = base64.b64encode(s.path.read_bytes()).decode("ascii")
        return f"data:{mime};base64,{b64}"
