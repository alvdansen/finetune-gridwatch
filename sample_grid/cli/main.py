"""`grid` CLI — the Phase-1 ``build`` subcommand (RUN-01).

Thin entrypoint: it owns argument parsing, the output directory layout, copying
populated samples into a self-contained ``assets/`` bundle, and auto-opening the
result (D-07). All grid logic lives in the pure core/render layers.
"""
from __future__ import annotations

import html
import shutil
import webbrowser
from pathlib import Path

import typer

from sample_grid.core.grid import build_grid
from sample_grid.core.model import CellState, GridConfig
from sample_grid.core.parse.filename import FilenameStubParser
from sample_grid.core.scan import Scanner
from sample_grid.render.renderer import render
from sample_grid.render.resolver import RelativeResolver

app = typer.Typer(
    add_completion=False,
    help="Build comparison grids from a folder of model samples.",
)

# The directory name created inside the user-supplied output base (D-06).
GRID_OUTPUT_DIRNAME = "grid-output"
ASSETS_DIRNAME = "assets"


@app.callback()
def _root() -> None:
    """Force multi-command (group) behavior so ``build`` stays a subcommand.

    Without a callback, Typer collapses a single-command app into a root command
    and ``build`` would be swallowed as a positional arg. The callback keeps room
    for the future ``watch`` (P4) and ``freeze`` (P5) siblings (D-05).
    """


def _empty_state_html(folder: Path) -> str:
    """A self-contained empty-state page (UI-SPEC Copywriting Contract)."""
    looked_in = html.escape(str(folder))
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en" data-theme="dark" data-density="comfortable">\n'
        "<head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>Sample Grid — no samples</title>"
        "<style>body{margin:0;min-height:100vh;display:flex;flex-direction:column;"
        "align-items:center;justify-content:center;background:#0e0f11;color:#e6e8eb;"
        "font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;"
        "text-align:center;padding:32px}h1{font-size:18px;font-weight:600;margin:0 0 16px}"
        "p{font-size:13px;line-height:1.45;color:#9aa0a6;max-width:42ch}</style></head>\n"
        "<body><h1>No samples found</h1>"
        f"<p>Point build at a folder containing .png, .jpg, or .webp files. "
        f"Looked in: {looked_in}</p></body></html>\n"
    )


@app.command()
def build(
    folder: Path = typer.Argument(..., help="Folder of model samples to grid."),
    output: Path = typer.Option(
        Path("."),
        "-o",
        "--output",
        help="Output base directory; the grid is written to <output>/grid-output/.",
    ),
    no_open: bool = typer.Option(
        False, "--no-open", help="Do not open the result in a browser (CI/scripts)."
    ),
    cell_size: int = typer.Option(
        240, "--cell-size", help="Cell width in px (default Comfortable)."
    ),
) -> None:
    """Build a static Steps × Prompts grid from FOLDER.

    Sample convention (Phase 1): the immediate parent directory is the prompt and
    the first integer in the filename is the training step —
    ``<prompt>/step_<N>.<ext>`` for .png/.jpg/.jpeg/.webp files.

    Writes ``<output>/grid-output/index.html`` plus a self-contained
    ``assets/`` bundle, then opens it in your browser (suppress with --no-open).
    """
    out_dir = output / GRID_OUTPUT_DIRNAME
    out_dir.mkdir(parents=True, exist_ok=True)
    index_path = out_dir / "index.html"

    files = Scanner().scan(folder)
    index = FilenameStubParser().parse(files)

    # Empty-state: never emit a silent content-free grid (UI-SPEC).
    if not index:
        message = (
            "No samples found. Point build at a folder containing "
            f".png, .jpg, or .webp files. Looked in: {folder}"
        )
        index_path.write_text(_empty_state_html(folder), encoding="utf-8")
        typer.echo(message, err=True)
        raise typer.Exit(0)

    grid = build_grid(index, GridConfig())

    # Copy each populated sample into the bundle, preserving its relative id path
    # so identical basenames across prompts never collide.
    resolver = RelativeResolver(assets_dir=ASSETS_DIRNAME)
    for row in grid.cells:
        for cell in row:
            if cell.state == CellState.POPULATED and cell.sample is not None:
                dest = out_dir / ASSETS_DIRNAME / Path(cell.sample.id)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(cell.sample.path, dest)

    html_str = render(
        grid, resolver, live=False, cell_size_px=cell_size
    )
    index_path.write_text(html_str, encoding="utf-8")

    typer.echo(f"Wrote {index_path}")
    if not no_open:
        webbrowser.open(index_path.resolve().as_uri())


if __name__ == "__main__":
    app()
