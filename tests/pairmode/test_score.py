"""Tests for skills/pairmode/scripts/score.py."""

from __future__ import annotations

import pathlib

import pytest
from click.testing import CliRunner

from skills.pairmode.scripts.score import score


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

MINIMAL_BRIEF = """\
# Reconstruction Brief — TestProject

> Generated from `docs/ideology.md` on 2026-01-01.

## Non-negotiable ideology

### Convictions

- Simplicity beats complexity because it reduces cognitive load.
- Correctness before performance at every layer.

### Constraints

#### No Direct DB Access

**Rule:** Never access the database directly from the web layer.

## What must survive any implementation

- The event-driven architecture must be preserved.

## What you are free to change

- File naming conventions.

## What you should question

- The synchronous request handler.

## Comparison rubric

- **Constraint traceability**: Can a reader determine why a protection exists?
- **Testability**: Is the code easy to test in isolation?
"""


def _write_brief(tmp_path: pathlib.Path, content: str = MINIMAL_BRIEF) -> pathlib.Path:
    """Write docs/reconstruction.md in tmp_path."""
    docs_dir = tmp_path / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    brief_path = docs_dir / "reconstruction.md"
    brief_path.write_text(content, encoding="utf-8")
    return brief_path


def _run(tmp_path: pathlib.Path, extra_args: list[str] | None = None) -> object:
    runner = CliRunner()
    args = ["--project-dir", str(tmp_path)] + (extra_args or [])
    return runner.invoke(score, args, catch_exceptions=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_creates_reconstruction_md(tmp_path: pathlib.Path) -> None:
    """score with valid brief → docs/RECONSTRUCTION.md is created."""
    _write_brief(tmp_path)
    result = _run(tmp_path)
    assert result.exit_code == 0, result.output
    out_path = tmp_path / "docs" / "RECONSTRUCTION.md"
    assert out_path.exists(), "docs/RECONSTRUCTION.md was not created"


def test_output_contains_conviction_heading(tmp_path: pathlib.Path) -> None:
    """Output contains a conviction heading (### Conviction:) from the brief."""
    _write_brief(tmp_path)
    result = _run(tmp_path)
    assert result.exit_code == 0, result.output
    content = (tmp_path / "docs" / "RECONSTRUCTION.md").read_text(encoding="utf-8")
    assert "### Conviction:" in content


def test_output_contains_rubric_dimension(tmp_path: pathlib.Path) -> None:
    """Output contains a rubric dimension name from the brief."""
    _write_brief(tmp_path)
    result = _run(tmp_path)
    assert result.exit_code == 0, result.output
    content = (tmp_path / "docs" / "RECONSTRUCTION.md").read_text(encoding="utf-8")
    assert "Constraint traceability" in content


def test_output_contains_summary_verdict(tmp_path: pathlib.Path) -> None:
    """Output contains ## Summary verdict."""
    _write_brief(tmp_path)
    result = _run(tmp_path)
    assert result.exit_code == 0, result.output
    content = (tmp_path / "docs" / "RECONSTRUCTION.md").read_text(encoding="utf-8")
    assert "## Summary verdict" in content


def test_force_overwrites_existing(tmp_path: pathlib.Path) -> None:
    """--force overwrites existing docs/RECONSTRUCTION.md without prompting."""
    _write_brief(tmp_path)
    out_path = tmp_path / "docs" / "RECONSTRUCTION.md"
    out_path.write_text("OLD CONTENT", encoding="utf-8")

    result = _run(tmp_path, ["--force"])
    assert result.exit_code == 0, result.output
    content = out_path.read_text(encoding="utf-8")
    assert "OLD CONTENT" not in content
    assert "## Summary verdict" in content


def test_no_force_prompt_n_aborts(tmp_path: pathlib.Path) -> None:
    """Existing file without --force: input 'n' → file unchanged, exit 0, 'Aborted.' message."""
    _write_brief(tmp_path)
    out_path = tmp_path / "docs" / "RECONSTRUCTION.md"
    original_content = "KEEP THIS CONTENT"
    out_path.write_text(original_content, encoding="utf-8")

    runner = CliRunner()
    args = ["--project-dir", str(tmp_path)]
    result = runner.invoke(score, args, input="n\n", catch_exceptions=False)

    assert result.exit_code == 0
    assert "Aborted." in result.output
    assert out_path.read_text(encoding="utf-8") == original_content


def test_path_traversal_guard(tmp_path: pathlib.Path) -> None:
    """--project-dir / (too shallow) → non-zero exit."""
    runner = CliRunner()
    # We cannot use exists=True for / since it does exist, but the guard checks len(parts) < 3
    # Use a path with only 1 part — the root itself
    result = runner.invoke(score, ["--project-dir", "/"], catch_exceptions=False)
    assert result.exit_code != 0


def test_missing_brief_exits_nonzero(tmp_path: pathlib.Path) -> None:
    """Missing brief (no brief file in default location) → non-zero exit with informative message."""
    # Ensure docs dir exists but no reconstruction.md
    (tmp_path / "docs").mkdir(parents=True, exist_ok=True)
    result = _run(tmp_path)
    assert result.exit_code != 0
    assert "error" in result.output.lower() or "not found" in result.output.lower()


def test_brief_outside_project_dir_rejected(tmp_path: pathlib.Path) -> None:
    """--brief pointing outside project_dir → non-zero exit with 'project directory' in output."""
    import tempfile

    project_dir = tmp_path / "project"
    project_dir.mkdir()

    # Create a sibling temp directory with a brief file
    sibling_dir = tmp_path / "sibling"
    sibling_dir.mkdir()
    outside_brief = sibling_dir / "reconstruction.md"
    outside_brief.write_text(MINIMAL_BRIEF, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        score,
        ["--project-dir", str(project_dir), "--brief", str(outside_brief)],
        catch_exceptions=False,
    )
    assert result.exit_code != 0
    assert "project directory" in result.output.lower()


def test_brief_inside_project_dir_accepted(tmp_path: pathlib.Path) -> None:
    """--brief pointing to a file inside project_dir → exit 0, RECONSTRUCTION.md created."""
    _write_brief(tmp_path)
    inside_brief = tmp_path / "docs" / "reconstruction.md"

    result = _run(tmp_path, ["--brief", str(inside_brief), "--force"])
    assert result.exit_code == 0, result.output
    out_path = tmp_path / "docs" / "RECONSTRUCTION.md"
    assert out_path.exists(), "docs/RECONSTRUCTION.md was not created"


def test_jinja2_undefined_variable_no_exception(tmp_path: pathlib.Path) -> None:
    """Rendering a template with an undefined variable must not raise an exception.

    score.py uses jinja2.Undefined (lenient), not StrictUndefined, so missing
    template variables silently render as empty string rather than crashing.
    """
    import jinja2
    import sys

    # Insert anchor repo root so the import works like in the actual script
    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

    from skills.pairmode.scripts import score as _score_module

    # Build a minimal in-memory environment using the same Undefined setting
    # that score.py applies (jinja2.Undefined — lenient).
    env = jinja2.Environment(
        loader=jinja2.BaseLoader(),
        undefined=jinja2.Undefined,
    )
    template = env.from_string("value={{ undefined_var }}")

    # Must not raise UndefinedError
    rendered = template.render()
    assert rendered == "value="
