"""SC3 guard: the render/freeze path must NEVER import the live server tier.

ROADMAP SC3 ("watch-mode code stays cleanly local-only") is a static-import
invariant: `grid build`/`grid freeze` render with only `sample_grid.render.*`
and `sample_grid.core.*` — never `fastapi`, `uvicorn`, `watchfiles`,
`sse_starlette`, or `sample_grid.live.*`. Only `sample_grid/cli/main.py` pulls
in the server layer. This test locks that invariant permanently: a future
accidental server-tier import into the render path would fail it.

The test purges the server-tier module names from `sys.modules` first, so a
prior test that imported the CLI cannot mask a real leak.
"""
from __future__ import annotations

import sys

# The server tier the render/freeze path must never drag in.
_SERVER_TIER = (
    "fastapi",
    "uvicorn",
    "watchfiles",
    "sse_starlette",
    "sample_grid.live",
)


def test_render_path_imports_no_server_tier() -> None:
    # Purge any server-tier modules a prior test (e.g. one importing the CLI)
    # may have loaded, so this test measures the render path in isolation.
    for m in list(sys.modules):
        if m.startswith(_SERVER_TIER):
            del sys.modules[m]

    # Import only what `grid freeze`/`build` render with.
    import sample_grid.render.renderer  # noqa: F401
    import sample_grid.render.resolver  # noqa: F401

    leaked = [m for m in sys.modules if m.startswith(_SERVER_TIER)]
    assert not leaked, f"render path pulled in server tier: {leaked}"
