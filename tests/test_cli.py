"""End-to-end CLI tests for the `grid build` walking skeleton."""
from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

runner = CliRunner()


# Scaffolds implemented in Task 3 (kept skipped so collection stays green
# while Tasks 1-2 land the detection core).
@pytest.mark.skip(reason="implemented in Task 3 (grid detect + silent build)")
def test_detect_reports() -> None:  # pragma: no cover - placeholder
    raise NotImplementedError


@pytest.mark.skip(reason="implemented in Task 3 (grid detect + silent build)")
def test_build_silent() -> None:  # pragma: no cover - placeholder
    raise NotImplementedError


def test_build_writes_html(dense_sample_folder: Path, tmp_path: Path) -> None:
    """`grid build` on a dense folder writes a browser-openable index.html.

    The dense fixture is 2 prompts x 3 steps = 6 populated coordinates, so the
    rendered page must carry exactly 6 `<img` tags — one per populated cell.
    """
    # Imported inside the test so the module still *collects* before the
    # implementation exists (Task 1 RED): collection is green, the test is red.
    from sample_grid.cli.main import app

    out = tmp_path / "out"
    result = runner.invoke(
        app,
        ["build", str(dense_sample_folder), "-o", str(out), "--no-open"],
    )

    assert result.exit_code == 0, result.output

    index_html = out / "grid-output" / "index.html"
    assert index_html.exists(), f"expected {index_html} to be written"

    html = index_html.read_text(encoding="utf-8")
    assert html.count("<img") == 6, f"expected 6 <img tags, found {html.count('<img')}"


def test_build_empty_folder(tmp_path: Path) -> None:
    """Building an empty folder writes a valid empty-state page and exits 0."""
    from sample_grid.cli.main import app

    empty = tmp_path / "empty"
    empty.mkdir()
    out = tmp_path / "out"

    result = runner.invoke(
        app, ["build", str(empty), "-o", str(out), "--no-open"]
    )

    assert result.exit_code == 0, result.output

    index_html = out / "grid-output" / "index.html"
    assert index_html.exists(), f"expected {index_html} to be written"
    assert "No samples found" in index_html.read_text(encoding="utf-8")
