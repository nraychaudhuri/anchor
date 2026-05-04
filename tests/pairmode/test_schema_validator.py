"""Tests for skills/pairmode/scripts/schema_validator.py"""

import sys
from pathlib import Path
import tempfile
import textwrap

import pytest

# Allow import of sibling scripts without installing the package
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"))

from schema_validator import (
    validate_story_file,
    validate_era_file,
    validate_phase_manifest,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(textwrap.dedent(content), encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# Story file tests
# ---------------------------------------------------------------------------

VALID_STORY = """\
    ---
    id: FEAT-001
    rail: FEAT
    title: My first story
    status: planned
    phase: "001"
    primary_files:
      - src/main.py
    ---

    ## Acceptance criterion

    It works.

    ## Instructions

    Do the thing.

    ## Tests

    Run the tests.
"""

def test_valid_story_file(tmp_path):
    p = _write(tmp_path, "FEAT-001.md", VALID_STORY)
    errors = validate_story_file(p)
    assert errors == [], f"Expected no errors, got: {errors}"


def test_story_missing_id(tmp_path):
    content = VALID_STORY.replace("id: FEAT-001\n", "")
    p = _write(tmp_path, "story.md", content)
    errors = validate_story_file(p)
    assert any("id" in e for e in errors), f"Expected 'id' error, got: {errors}"


def test_story_missing_primary_files(tmp_path):
    # Remove the primary_files block entirely
    lines = textwrap.dedent(VALID_STORY).splitlines(keepends=True)
    filtered = [
        line for line in lines
        if "primary_files" not in line and "src/main.py" not in line
    ]
    p = _write(tmp_path, "story.md", "".join(filtered))
    errors = validate_story_file(p)
    assert any("primary_files" in e for e in errors), f"Expected 'primary_files' error, got: {errors}"


def test_story_invalid_status(tmp_path):
    content = VALID_STORY.replace("status: planned", "status: unknown-status")
    p = _write(tmp_path, "story.md", content)
    errors = validate_story_file(p)
    assert any("status" in e.lower() for e in errors), f"Expected status error, got: {errors}"


def test_story_draft_empty_primary_files_allowed(tmp_path):
    """status: draft with empty primary_files must not produce an error."""
    content = (
        VALID_STORY
        .replace("status: planned", "status: draft")
        .replace("  - src/main.py\n", "")
    )
    p = _write(tmp_path, "story.md", content)
    errors = validate_story_file(p)
    assert not any("primary_files" in e for e in errors), (
        f"Expected no primary_files error for draft story, got: {errors}"
    )


def test_story_backlog_empty_primary_files_allowed(tmp_path):
    """status: backlog with empty primary_files must not produce an error."""
    content = (
        VALID_STORY
        .replace("status: planned", "status: backlog")
        .replace("  - src/main.py\n", "")
    )
    p = _write(tmp_path, "story.md", content)
    errors = validate_story_file(p)
    assert not any("primary_files" in e for e in errors), (
        f"Expected no primary_files error for backlog story, got: {errors}"
    )


def test_story_planned_empty_primary_files_errors(tmp_path):
    """status: planned with empty primary_files must produce an error."""
    content = VALID_STORY.replace("  - src/main.py\n", "")
    p = _write(tmp_path, "story.md", content)
    errors = validate_story_file(p)
    assert any("primary_files" in e for e in errors), (
        f"Expected primary_files error for planned story, got: {errors}"
    )


def test_story_complete_with_primary_files_no_error(tmp_path):
    """status: complete with non-empty primary_files must not produce an error."""
    content = VALID_STORY.replace("status: planned", "status: complete")
    p = _write(tmp_path, "story.md", content)
    errors = validate_story_file(p)
    assert errors == [], f"Expected no errors for complete story with files, got: {errors}"


# ---------------------------------------------------------------------------
# Era file tests
# ---------------------------------------------------------------------------

VALID_ERA = """\
    ---
    id: "001"
    name: Foundation Era
    status: active
    ---

    ## Strategic intent

    Build the foundation.

    ## Rails

    | Rail | Primary domain |
    |------|----------------|
    | FEAT | Core features |

    ## Phases

    | Phase | Title |
    |-------|-------|
    | 001 | Kickoff |
"""


def test_valid_era_file(tmp_path):
    p = _write(tmp_path, "001-foundation.md", VALID_ERA)
    errors = validate_era_file(p)
    assert errors == [], f"Expected no errors, got: {errors}"


def test_era_missing_status(tmp_path):
    # Dedent first so the replacement operates on the normalised text
    content = textwrap.dedent(VALID_ERA).replace("status: active\n", "")
    p = tmp_path / "era.md"
    p.write_text(content, encoding="utf-8")
    errors = validate_era_file(p)
    assert any("status" in e for e in errors), f"Expected 'status' error, got: {errors}"


# ---------------------------------------------------------------------------
# Phase manifest tests
# ---------------------------------------------------------------------------

VALID_PHASE_MANIFEST = """\
    ---
    era: "001"
    ---

    ## Goal

    Ship story 15.0.

    ## Stories

    | ID | Title | Status |
    |----|-------|--------|
    | FEAT-001 | My first story | planned |
"""


def test_valid_phase_manifest(tmp_path):
    p = _write(tmp_path, "phase-15.md", VALID_PHASE_MANIFEST)
    errors = validate_phase_manifest(p)
    assert errors == [], f"Expected no errors, got: {errors}"


def test_phase_manifest_missing_era(tmp_path):
    # Dedent first so the replacement operates on the normalised text
    content = textwrap.dedent(VALID_PHASE_MANIFEST).replace('era: "001"\n', "")
    p = tmp_path / "phase.md"
    p.write_text(content, encoding="utf-8")
    errors = validate_phase_manifest(p)
    assert any("era" in e for e in errors), f"Expected 'era' error, got: {errors}"
