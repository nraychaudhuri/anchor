"""Tests for skills/pairmode/scripts/reconstruct.py."""

from __future__ import annotations

import pathlib
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from skills.pairmode.scripts.reconstruct import reconstruct


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_ideology(tmp_path: pathlib.Path, content: str) -> pathlib.Path:
    """Write docs/ideology.md in tmp_path."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    ideology_path = docs_dir / "ideology.md"
    ideology_path.write_text(content, encoding="utf-8")
    return ideology_path


MINIMAL_IDEOLOGY = """\
# Ideology — TestProject

## Core convictions

- We prefer simplicity over complexity because it reduces bugs.

## Value hierarchy

- Correctness over performance at this stage.

## Accepted constraints

### No Direct DB Access

**Rule:** Never access the database directly from the web layer.

**Rationale:** Keeps the data layer isolated and testable.

## Prototype fingerprints

_(No prototype fingerprints recorded.)_

## Reconstruction guidance

### Must preserve

- The event-driven architecture must be preserved.

### Should question

- The synchronous request handler.

### Free to change

- The file naming conventions.

## Comparison basis

- **Constraint traceability:** Can a reader determine why a protection exists?
"""

MINIMAL_BRIEF = """\
# Brief — TestProject

## What this project produces

A structured builder/reviewer workflow for any project.

## Why it exists

To give AI agents persistent memory of architectural decisions.
"""


def _run(tmp_path: pathlib.Path, extra_args: list[str] | None = None) -> object:
    runner = CliRunner()
    args = ["--project-dir", str(tmp_path)] + (extra_args or [])
    return runner.invoke(reconstruct, args, catch_exceptions=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_writes_reconstruction_with_conviction(tmp_path: pathlib.Path) -> None:
    """Populated ideology.md → reconstruction.md written; conviction appears in output."""
    _write_ideology(tmp_path, MINIMAL_IDEOLOGY)
    result = _run(tmp_path)
    assert result.exit_code == 0, result.output
    out_path = tmp_path / "docs" / "reconstruction.md"
    assert out_path.exists()
    content = out_path.read_text(encoding="utf-8")
    assert "simplicity over complexity" in content


def test_missing_ideology_exits_nonzero(tmp_path: pathlib.Path) -> None:
    """Missing ideology.md → exits non-zero with error message in output."""
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    runner = CliRunner()
    result = runner.invoke(reconstruct, ["--project-dir", str(tmp_path)], catch_exceptions=False)
    assert result.exit_code != 0
    assert "ideology.md" in result.output


def test_existing_reconstruction_no_force_aborts(tmp_path: pathlib.Path) -> None:
    """Existing reconstruction.md + no --force → click.confirm called; no overwrite on 'no'."""
    _write_ideology(tmp_path, MINIMAL_IDEOLOGY)
    existing_content = "ORIGINAL CONTENT"
    out_path = tmp_path / "docs" / "reconstruction.md"
    out_path.write_text(existing_content, encoding="utf-8")

    with patch("click.confirm", return_value=False) as mock_confirm:
        result = _run(tmp_path)
        mock_confirm.assert_called_once()

    # File should not be overwritten
    assert out_path.read_text(encoding="utf-8") == existing_content


def test_existing_reconstruction_with_force_overwrites(tmp_path: pathlib.Path) -> None:
    """Existing reconstruction.md + --force → file overwritten without prompting."""
    _write_ideology(tmp_path, MINIMAL_IDEOLOGY)
    out_path = tmp_path / "docs" / "reconstruction.md"
    out_path.write_text("OLD CONTENT", encoding="utf-8")

    with patch("click.confirm") as mock_confirm:
        result = _run(tmp_path, ["--force"])
        mock_confirm.assert_not_called()

    assert result.exit_code == 0
    content = out_path.read_text(encoding="utf-8")
    assert "OLD CONTENT" not in content
    assert "Reconstruction" in content or "reconstruction" in content


def test_path_traversal_guard(tmp_path: pathlib.Path) -> None:
    """--project-dir / exits with error (path too shallow)."""
    runner = CliRunner()
    result = runner.invoke(reconstruct, ["--project-dir", "/"], catch_exceptions=False)
    assert result.exit_code != 0


def test_brief_what_appears_in_output(tmp_path: pathlib.Path) -> None:
    """brief.md ## What this project produces body appears as reconstruction_what."""
    _write_ideology(tmp_path, MINIMAL_IDEOLOGY)
    brief_path = tmp_path / "docs" / "brief.md"
    brief_path.write_text(MINIMAL_BRIEF, encoding="utf-8")

    result = _run(tmp_path)
    assert result.exit_code == 0
    content = (tmp_path / "docs" / "reconstruction.md").read_text(encoding="utf-8")
    assert "structured builder/reviewer workflow" in content


def test_instructions_section_present(tmp_path: pathlib.Path) -> None:
    """Rendered output contains ## Instructions for the reconstruction agent."""
    _write_ideology(tmp_path, MINIMAL_IDEOLOGY)
    result = _run(tmp_path)
    assert result.exit_code == 0
    content = (tmp_path / "docs" / "reconstruction.md").read_text(encoding="utf-8")
    assert "## Instructions for the reconstruction agent" in content


def test_must_preserve_bullet_in_output(tmp_path: pathlib.Path) -> None:
    """ideology.md ### Must preserve bullet appears in rendered reconstruction.md."""
    _write_ideology(tmp_path, MINIMAL_IDEOLOGY)
    result = _run(tmp_path)
    assert result.exit_code == 0
    content = (tmp_path / "docs" / "reconstruction.md").read_text(encoding="utf-8")
    assert "event-driven architecture" in content
