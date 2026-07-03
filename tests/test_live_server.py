"""Server-slice tests for the live-watch FastAPI app (RUN-02).

Exercises ``build_app`` directly via Starlette's ``TestClient`` (no Uvicorn loop):
  * ``/media/{id}`` seeks via HTTP ``Range`` → ``206 Partial Content`` (video
    scrubbing) and serves a plain ``200`` otherwise (T-4-01 surface);
  * ``/media`` rejects a ``..`` traversal id and NEVER serves an out-of-root file
    (T-4-01 path-confinement, reusing ``util.paths.confine``);
  * ``/events`` is ``text/event-stream`` and a ``Broadcaster.broadcast(...)`` reaches
    a subscribed queue.

The three tests import ``build_app`` / ``Broadcaster`` from ``sample_grid.live.server``
inside the test bodies so the module still COLLECTS before the implementation exists
(Task 1 RED): collection is green, the assertions are red until Task 2 lands.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from starlette.testclient import TestClient


def _served_root(tmp_path: Path) -> Path:
    """A tiny scan root with one media file the /media route can serve."""
    root = tmp_path / "outputs"
    media = root / "a_lake" / "step_600.mp4"
    media.parent.mkdir(parents=True, exist_ok=True)
    # 4 KB of bytes so a Range request has something to partition.
    media.write_bytes(b"\0" * 4096)
    return root


def _make_client(root: Path):
    from sample_grid.live.server import Broadcaster, build_app

    broadcaster = Broadcaster()
    app = build_app(
        root=root,
        page_html_getter=lambda: "<!DOCTYPE html><title>live</title>",
        broadcaster=broadcaster,
    )
    return TestClient(app), broadcaster


def test_media_range_206(tmp_path: Path) -> None:
    """A ``Range: bytes=0-1`` request returns 206 + a partial body; a plain GET is 200."""
    root = _served_root(tmp_path)
    client, _ = _make_client(root)

    plain = client.get("/media/a_lake/step_600.mp4")
    assert plain.status_code == 200
    assert len(plain.content) == 4096

    ranged = client.get(
        "/media/a_lake/step_600.mp4", headers={"Range": "bytes=0-1"}
    )
    assert ranged.status_code == 206, ranged.status_code
    # A partial-content body is strictly smaller than the whole file.
    assert len(ranged.content) < 4096
    assert ranged.headers.get("content-range", "").startswith("bytes 0-1/")


def test_media_confined(tmp_path: Path) -> None:
    """A traversal id is rejected (4xx) and never serves an out-of-root file."""
    root = _served_root(tmp_path)
    # A secret sitting OUTSIDE the scan root — a successful traversal would leak it.
    secret = tmp_path / "secret.txt"
    secret.write_text("top secret", encoding="utf-8")

    client, _ = _make_client(root)

    resp = client.get("/media/../secret.txt")
    assert resp.status_code >= 400, resp.status_code
    assert "top secret" not in resp.text


def _events_response_start(app) -> dict:
    """Drive ``GET /events`` at the ASGI layer and capture ``http.response.start``.

    A live SSE stream never ends on its own, so a ``TestClient`` stream would block
    its own close (the server generator parks on ``queue.get()``). Instead we speak
    ASGI directly and answer the stream's disconnect probe with ``http.disconnect``
    so the endpoint terminates deterministically — capturing the status + headers
    that carry the ``text/event-stream`` content-type contract.
    """
    captured: dict = {}

    async def _drive() -> None:
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/events",
            "raw_path": b"/events",
            "query_string": b"",
            "root_path": "",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("127.0.0.1", 8000),
        }
        sent_request = False

        async def receive():
            nonlocal sent_request
            if not sent_request:
                sent_request = True
                return {"type": "http.request", "body": b"", "more_body": False}
            # The stream polls for disconnect — report one so it exits cleanly.
            return {"type": "http.disconnect"}

        async def send(message) -> None:
            if message["type"] == "http.response.start":
                captured["status"] = message["status"]
                captured["headers"] = {
                    k.decode().lower(): v.decode() for k, v in message["headers"]
                }

        await asyncio.wait_for(app(scope, receive, send), timeout=5.0)

    asyncio.run(_drive())
    return captured


def test_events_broadcast(tmp_path: Path) -> None:
    """``/events`` is text/event-stream and a broadcast reaches a subscribed queue."""
    root = _served_root(tmp_path)
    _, broadcaster = _make_client(root)
    from sample_grid.live.server import build_app

    app = build_app(root=root, page_html_getter=lambda: "<x>", broadcaster=broadcaster)

    # Content-type contract: the SSE stream announces text/event-stream.
    start = _events_response_start(app)
    assert start.get("status") == 200
    assert start.get("headers", {}).get("content-type", "").startswith(
        "text/event-stream"
    )

    # Broadcaster fan-out: a subscribed queue receives the JSON-encoded patch.
    async def _roundtrip() -> dict:
        q = broadcaster.subscribe()
        await broadcaster.broadcast({"op": "replace_cell", "r": 0, "c": 0, "html": "<x>"})
        item = await asyncio.wait_for(q.get(), timeout=1.0)
        broadcaster.unsubscribe(q)
        return item

    item = asyncio.run(_roundtrip())
    # The Broadcaster hands sse-starlette a {"data": <json>} envelope.
    assert "data" in item
    assert '"replace_cell"' in item["data"]
