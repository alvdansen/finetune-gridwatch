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


def test_events_broadcast(tmp_path: Path) -> None:
    """``/events`` is text/event-stream and a broadcast reaches a subscribed queue."""
    root = _served_root(tmp_path)
    client, broadcaster = _make_client(root)

    # Content-type contract: the SSE stream must announce text/event-stream.
    with client.stream("GET", "/events") as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

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
