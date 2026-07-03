"""Live-watch FastAPI app: page + Range-capable ``/media`` + SSE ``/events`` (RUN-02).

Three routes, one broadcaster — the server half of the live loop:

* ``GET /`` → the current served page HTML (from ``page_html_getter()``); the
  ``watch`` command keeps that getter pointed at the latest full render.
* ``GET /media/{id:path}`` → the media file at the posix-relative ``Sample.id``.
  The ``id`` is URL-decoded, resolved under the scan ``root``, and passed through
  :func:`sample_grid.util.paths.confine` BEFORE any read, so a ``..``/symlink
  escape is rejected (``ValueError`` → 404) and never serves an out-of-root file
  (T-4-01). Starlette's :class:`FileResponse` handles HTTP ``Range`` and returns
  ``206 Partial Content`` — the byte-range seeking that makes video scrubbing work
  over the served path. Byte ranges are NOT hand-rolled (Don't-Hand-Roll).
* ``GET /events`` → an :class:`EventSourceResponse` (``ping=15`` keep-alive) that
  streams JSON patch envelopes from a per-client :class:`asyncio.Queue`. The
  browser ``EventSource`` auto-reconnects on drop; no replay protocol (MVP — the
  next re-scan self-heals).

The server binds ``127.0.0.1`` ONLY (the CLI owns the bind in Task 3) — it serves
the user's private sample folder, never the LAN (T-4-03). All patch markup is
server-rendered upstream (04-01 macros, autoescape ON); the server only fans out
the already-escaped JSON envelope (T-4-02) — it never f-strings cell HTML.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Callable
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException, Request
from sse_starlette import EventSourceResponse
from starlette.responses import FileResponse, HTMLResponse

from sample_grid.util.paths import confine


class Broadcaster:
    """Fan-out of live patch envelopes to every connected SSE client.

    One :class:`asyncio.Queue` per subscribed ``/events`` connection.
    :meth:`broadcast` JSON-encodes the patch dict and ``put_nowait``s a
    sse-starlette ``{"data": <json>}`` envelope onto every queue; the per-client
    generator in :func:`build_app` drains its own queue. JSON-encoding the HTML
    string sidesteps the SSE newline-framing rule (``data:`` splits on ``\\n``) —
    the client ``JSON.parse``s exactly one line.
    """

    def __init__(self) -> None:
        self.queues: "list[asyncio.Queue]" = []

    def subscribe(self) -> "asyncio.Queue":
        q: "asyncio.Queue" = asyncio.Queue()
        self.queues.append(q)
        return q

    def unsubscribe(self, q: "asyncio.Queue") -> None:
        # Idempotent — a double-unsubscribe (disconnect race) must never raise.
        if q in self.queues:
            self.queues.remove(q)

    async def broadcast(self, patch: dict) -> None:
        """JSON-encode ``patch`` and enqueue it for every subscribed client."""
        data = json.dumps(patch)
        for q in self.queues:
            q.put_nowait({"data": data})


def build_app(
    root: Path,
    page_html_getter: "Callable[[], str]",
    broadcaster: Broadcaster,
) -> FastAPI:
    """Assemble the live-watch FastAPI app over a confined media ``root``."""
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
    root = Path(root)

    @app.get("/")
    async def index() -> HTMLResponse:  # noqa: D401 — route body
        return HTMLResponse(page_html_getter())

    @app.get("/media/{id:path}")
    async def media(id: str) -> FileResponse:  # noqa: A002 — SSE/route id name
        # URL-decode first (spaces → %20, etc.), resolve under root, THEN confine:
        # any `..`/symlink escape raises ValueError → 404, never serving the file.
        target = (root / unquote(id)).resolve()
        try:
            confine(root.resolve(), target)
        except ValueError:
            raise HTTPException(status_code=404, detail="Not found")
        if not target.is_file():
            raise HTTPException(status_code=404, detail="Not found")
        # Starlette FileResponse handles Range → 206 partial content (video seek).
        return FileResponse(target)

    @app.get("/events")
    async def events(request: Request) -> EventSourceResponse:
        q = broadcaster.subscribe()

        async def stream():
            try:
                while True:
                    if await request.is_disconnected():
                        break
                    yield await q.get()
            finally:
                broadcaster.unsubscribe(q)

        return EventSourceResponse(stream(), ping=15)

    return app
