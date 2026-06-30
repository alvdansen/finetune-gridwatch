# sample-html-generator

A video-first **model-comparison grid builder** for evaluating generative-model
samples. Point it at a training/inference output folder and it renders an HTML
grid — by default **training-steps × prompts** — to watch a single LoRA or
checkpoint evolve over a run.

## Quick start

Arrange your samples following the Phase-1 convention (immediate parent folder =
prompt, first integer in the filename = step):

```
outputs/
  a serene lake/
    step_200.png
    step_600.png
    step_1000.png
  a city street/
    step_200.png
    ...
```

Then build a self-contained grid:

```bash
grid build ./outputs -o ./out
```

This writes `./out/grid-output/index.html` (plus a copied `assets/` folder) and
opens it in your browser. Pass `--no-open` to skip the browser (CI/scripts) and
`--cell-size <px>` to change the cell width.

The output is a single, server-free page: open `index.html` directly from disk.

## Status

Phase 1 — the walking skeleton: static **Steps × Prompts** image grid. Video
cells (Phase 3), live watch (Phase 4), and freeze/export (Phase 5) follow.
