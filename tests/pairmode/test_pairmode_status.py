"""Tests for skills/pairmode/scripts/pairmode_status.py."""

from __future__ import annotations

import json
import pathlib
import sys

from click.testing import CliRunner

# Add scripts dir for direct import (matches pattern used by other tests)
sys.path.insert(
    0,
    str(pathlib.Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"),
)

from pairmode_status import pairmode_status  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_state(project_dir: pathlib.Path, state: dict) -> pathlib.Path:
    """Write .companion/state.json under *project_dir* with the given state."""
    companion_dir = project_dir / ".companion"
    companion_dir.mkdir(parents=True, exist_ok=True)
    state_path = companion_dir / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return state_path


def _invoke(project_dir: pathlib.Path):
    runner = CliRunner()
    return runner.invoke(
        pairmode_status,
        ["--project-dir", str(project_dir)],
        catch_exceptions=False,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_not_a_pairmode_repo(tmp_path: pathlib.Path) -> None:
    """No state.json present → exit 0 with 'Not a pairmode repo' message."""
    result = _invoke(tmp_path)
    assert result.exit_code == 0, result.output
    assert "Not a pairmode repo" in result.output


def test_shows_version(tmp_path: pathlib.Path) -> None:
    """state.json with pairmode_version → version appears in output."""
    _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    result = _invoke(tmp_path)
    assert result.exit_code == 0, result.output
    assert "0.1.0" in result.output
    assert "Pairmode v0.1.0" in result.output


def test_shows_current_story(tmp_path: pathlib.Path) -> None:
    """state.json with current_story → story ID appears in output."""
    _write_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "current_story": {
                "id": "INFRA-014",
                "title": "Close targeted test gaps",
                "status": "in-progress",
            },
        },
    )
    result = _invoke(tmp_path)
    assert result.exit_code == 0, result.output
    assert "INFRA-014" in result.output


def test_shows_no_story(tmp_path: pathlib.Path) -> None:
    """state.json without current_story → '(none set)' appears in output."""
    _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    result = _invoke(tmp_path)
    assert result.exit_code == 0, result.output
    assert "(none set)" in result.output


def test_shows_sidebar_active(tmp_path: pathlib.Path) -> None:
    """pipe_path pointing at a real file → 'Sidebar: active' in output."""
    pipe_file = tmp_path / "fake.pipe"
    pipe_file.write_text("", encoding="utf-8")
    _write_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "pipe_path": str(pipe_file),
        },
    )
    result = _invoke(tmp_path)
    assert result.exit_code == 0, result.output
    assert "Sidebar: active" in result.output
    assert str(pipe_file) in result.output


def test_shows_attachment_instructions(tmp_path: pathlib.Path) -> None:
    """pipe_path pointing at non-existent path → attachment instructions emitted."""
    missing_pipe = tmp_path / "does_not_exist.pipe"
    _write_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "pipe_path": str(missing_pipe),
        },
    )
    result = _invoke(tmp_path)
    assert result.exit_code == 0, result.output
    assert "start_sidebar.sh" in result.output
    assert "tail -f" in result.output


def test_start_sidebar_path_exists(tmp_path: pathlib.Path) -> None:
    """The printed ``bash <start_sidebar.sh>`` path must resolve to a real file.

    Regression guard for CER-012: ``ANCHOR_ROOT`` previously resolved to
    ``<repo>/skills/`` instead of the anchor repo root, producing a
    ``<repo>/skills/skills/companion/scripts/start_sidebar.sh`` instruction
    that pointed at a non-existent file.
    """
    missing_pipe = tmp_path / "does_not_exist.pipe"
    _write_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "pipe_path": str(missing_pipe),
        },
    )
    result = _invoke(tmp_path)
    assert result.exit_code == 0, result.output

    # Extract the start_sidebar.sh path from any "bash <path>" line.
    extracted: str | None = None
    for raw_line in result.output.splitlines():
        line = raw_line.strip()
        if line.startswith("macOS:") or line.startswith("Linux"):
            # Each line looks like:  "macOS:         bash /path/to/start_sidebar.sh"
            idx = line.find("bash ")
            if idx != -1:
                extracted = line[idx + len("bash ") :].strip()
                break

    assert extracted is not None, (
        f"Could not find a 'bash <start_sidebar.sh>' instruction in output:\n{result.output}"
    )
    assert extracted.endswith("start_sidebar.sh"), extracted
    assert pathlib.Path(extracted).exists(), (
        f"start_sidebar.sh path printed to user does not exist on disk: {extracted}"
    )


def test_shows_modules(tmp_path: pathlib.Path) -> None:
    """state.json with last_loaded_modules → all modules appear in output."""
    _write_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "last_loaded_modules": ["pairmode-skill", "docs"],
        },
    )
    result = _invoke(tmp_path)
    assert result.exit_code == 0, result.output
    assert "pairmode-skill" in result.output
    assert "docs" in result.output


def test_shows_active_era(tmp_path: pathlib.Path) -> None:
    """An era file with status: active → era id and name appear in output."""
    _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    eras_dir = tmp_path / "docs" / "eras"
    eras_dir.mkdir(parents=True, exist_ok=True)
    (eras_dir / "001-initial.md").write_text(
        '---\nid: "001"\nname: Initial development\nstatus: active\n---\n',
        encoding="utf-8",
    )
    result = _invoke(tmp_path)
    assert result.exit_code == 0, result.output
    assert "001" in result.output
    assert "Initial development" in result.output


def test_no_active_era(tmp_path: pathlib.Path) -> None:
    """No era files → '(none)' appears for the era line."""
    _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    result = _invoke(tmp_path)
    assert result.exit_code == 0, result.output
    assert "Era:     (none)" in result.output


def test_no_pairmode_version_treated_as_non_pairmode(tmp_path: pathlib.Path) -> None:
    """state.json exists but pairmode_version absent → 'Not a pairmode repo'."""
    _write_state(tmp_path, {"some_other_key": "value"})
    result = _invoke(tmp_path)
    assert result.exit_code == 0, result.output
    assert "Not a pairmode repo" in result.output
