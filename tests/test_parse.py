"""Auto-detect picker + per-field precedence merge + source extractors.

Task 1 drives ``merge_fields`` / ``AutoDetectParser`` directly with hand-built
per-source ``FieldValue`` maps (inline stub extractors satisfying the
``Extractor`` Protocol — no on-disk parsing needed). Task 2 adds the real
``FilenameExtractor`` / ``SubfolderExtractor`` tests further down.
"""
from __future__ import annotations

from pathlib import Path

from sample_grid.core.parse.base import (
    SOURCE_PRECEDENCE,
    AutoDetectParser,
    DetectionReport,
    Extractor,
    FieldValue,
    merge_fields,
)


def test_precedence_merge() -> None:
    """Same value from both sources merges once (no conflict); different values
    resolve to the higher-precedence source (filename > subfolder, D-03)."""
    report = DetectionReport()
    agree = {
        "filename": {"step": FieldValue(600, "filename", 1.0)},
        "subfolder": {"step": FieldValue(600, "subfolder", 0.4)},
    }
    merged = merge_fields(agree, report)
    assert merged["step"] == 600
    assert report.conflicts == []

    report2 = DetectionReport()
    disagree = {
        "filename": {"step": FieldValue(600, "filename", 1.0)},
        "subfolder": {"step": FieldValue(500, "subfolder", 0.4)},
    }
    merged2 = merge_fields(disagree, report2)
    # filename outranks subfolder — its value wins.
    assert merged2["step"] == 600
    assert SOURCE_PRECEDENCE["filename"] > SOURCE_PRECEDENCE["subfolder"]


def test_conflict_report() -> None:
    """Differing values across sources append a (field, [(source, value)]) entry
    to DetectionReport.conflicts (D-04)."""
    report = DetectionReport()
    per_source = {
        "filename": {"step": FieldValue(600, "filename", 1.0)},
        "subfolder": {"step": FieldValue(500, "subfolder", 0.4)},
    }
    merge_fields(per_source, report)

    assert len(report.conflicts) == 1
    fieldname, candidates = report.conflicts[0]
    assert fieldname == "step"
    assert ("filename", 600) in candidates
    assert ("subfolder", 500) in candidates


class _StubExtractor:
    """Inline Extractor (Protocol-conformant) for the picker skip test."""

    def extract(self, files: list[Path]) -> dict[str, dict[str, FieldValue]]:
        out: dict[str, dict[str, FieldValue]] = {}
        for f in files:
            if "step_600" in Path(f).name:
                out["a_lake/step_600.png"] = {
                    "step": FieldValue(600, "filename", 1.0),
                    "prompt": FieldValue("a_lake", "subfolder", 0.4),
                }
        return out


def test_skip_unclassifiable(tmp_path: Path) -> None:
    """A file no extractor classifies is excluded from the index and appended to
    DetectionReport.skipped; parse() returns (SampleIndex, DetectionReport)."""
    good = tmp_path / "a_lake" / "step_600.png"
    good.parent.mkdir(parents=True, exist_ok=True)
    good.write_bytes(b"\x89PNG stub")
    bad = tmp_path / "a_lake" / "notes.png"
    bad.write_bytes(b"\x89PNG stub")

    # The stub satisfies the runtime-checkable Extractor Protocol.
    assert isinstance(_StubExtractor(), Extractor)

    index, report = AutoDetectParser([_StubExtractor()]).parse([good, bad])

    assert len(index) == 1
    assert index[0].dims["step"] == 600
    assert index[0].dims["prompt"] == "a_lake"
    assert index[0].path == good
    # The no-integer file is skipped and counted (D-05).
    assert report.n_files == 2
    assert len(report.skipped) == 1


# ---------------------------------------------------------------------------
# Task 2: real filename / subfolder extractors
# ---------------------------------------------------------------------------


def test_filename_extract(aitoolkit_style_folder: Path) -> None:
    """META-01: labeled tokens (step_600_seed42) and ai-toolkit structural names
    (9-digit zero-padded step + trailing sample index) → per-field FieldValues,
    source="filename", prompt surfaced as the integer index for ai-toolkit (A2)."""
    from sample_grid.core.parse.filename import FilenameExtractor
    from sample_grid.core.scan import Scanner

    # Labeled tokens: step_600_seed42 under a prompt folder.
    labeled = aitoolkit_style_folder.parent / "labeled"
    (labeled / "a_lake").mkdir(parents=True, exist_ok=True)
    f = labeled / "a_lake" / "step_600_seed42.png"
    f.write_bytes(b"x")

    out = FilenameExtractor().extract([f])
    (fields,) = out.values()
    assert fields["step"].value == 600
    assert fields["step"].source == "filename"
    assert fields["seed"].value == 42
    assert fields["seed"].source == "filename"
    assert fields["prompt"].value == "a_lake"

    # ai-toolkit: 20260630__000000600_3.jpg → step=600, prompt=index 3 (A2).
    ai_files = Scanner().scan(aitoolkit_style_folder)
    ai_out = FilenameExtractor().extract(ai_files)
    sample_fields = next(iter(ai_out.values()))
    assert sample_fields["step"].value == 600
    # prompt surfaced as the integer sample index — no index→text resolution.
    assert sample_fields["prompt"].value == 3


def test_subfolder_extract(tmp_path: Path) -> None:
    """META-02: parent dir → prompt (source=subfolder); a deeper step_<N> path
    segment yields step at source=subfolder (lowest precedence)."""
    from sample_grid.core.parse.subfolder import SubfolderExtractor

    flat = tmp_path / "a_lake" / "whatever.png"
    flat.parent.mkdir(parents=True, exist_ok=True)
    flat.write_bytes(b"x")

    deep = tmp_path / "a_city" / "step_500" / "x.png"
    deep.parent.mkdir(parents=True, exist_ok=True)
    deep.write_bytes(b"x")

    out = SubfolderExtractor().extract([flat, deep])

    flat_key = next(k for k in out if k.endswith("whatever.png"))
    assert out[flat_key]["prompt"].value == "a_lake"
    assert out[flat_key]["prompt"].source == "subfolder"

    deep_key = next(k for k in out if k.endswith("x.png"))
    assert out[deep_key]["step"].value == 500
    assert out[deep_key]["step"].source == "subfolder"
    assert out[deep_key]["prompt"].value == "a_city"
