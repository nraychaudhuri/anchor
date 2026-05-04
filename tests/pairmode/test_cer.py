"""Tests for cer.py — CER triage CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from skills.pairmode.scripts.cer import (
    cli,
    append_finding,
    _escape_table_cell,
    _load_or_create_backlog,
    _next_cer_id,
    _parse_entries_from_backlog,
    BACKLOG_REL_PATH,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _backlog_path(project_dir: Path) -> Path:
    return project_dir / BACKLOG_REL_PATH


def _invoke(runner: CliRunner, args: list[str], input: str | None = None):
    return runner.invoke(cli, args, input=input, catch_exceptions=False)


# ---------------------------------------------------------------------------
# Test: creates backlog.md when it does not exist
# ---------------------------------------------------------------------------

def test_creates_backlog_when_missing(tmp_path: Path) -> None:
    backlog = _backlog_path(tmp_path)
    assert not backlog.exists()

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Missing auth check on admin endpoint",
            "--quadrant", "now",
        ],
    )
    assert result.exit_code == 0, result.output
    assert backlog.exists()
    content = backlog.read_text(encoding="utf-8")
    assert "Missing auth check on admin endpoint" in content
    assert "CER-001" in content


# ---------------------------------------------------------------------------
# Test: appends entry to the correct quadrant section
# ---------------------------------------------------------------------------

def test_appends_to_correct_quadrant(tmp_path: Path) -> None:
    runner = CliRunner()

    # Insert one finding in each quadrant
    quadrants = [
        ("now", "Do Now"),
        ("later", "Do Later"),
        ("much_later", "Do Much Later"),
    ]
    for q, _section in quadrants:
        result = _invoke(
            runner,
            [
                "--project-dir", str(tmp_path),
                "--finding", f"Finding for {q}",
                "--quadrant", q,
            ],
        )
        assert result.exit_code == 0, result.output

    content = _backlog_path(tmp_path).read_text(encoding="utf-8")

    # Each finding should appear under its correct section
    lines = content.splitlines()
    section_to_findings: dict[str, list[str]] = {
        "## Do Now": [],
        "## Do Later": [],
        "## Do Much Later": [],
    }
    current_section: str | None = None
    for line in lines:
        s = line.strip()
        if s in section_to_findings:
            current_section = s
        elif current_section and s.startswith("| CER-"):
            section_to_findings[current_section].append(s)

    assert any("Finding for now" in row for row in section_to_findings["## Do Now"])
    assert any("Finding for later" in row for row in section_to_findings["## Do Later"])
    assert any("Finding for much_later" in row for row in section_to_findings["## Do Much Later"])


# ---------------------------------------------------------------------------
# Test: never without resolution exits 1
# ---------------------------------------------------------------------------

def test_never_without_resolution_exits_1(tmp_path: Path) -> None:
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Low-value cosmetic thing",
            "--quadrant", "never",
            # no --resolution
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 1
    assert "resolution" in result.output.lower() or "resolution" in (result.exception or Exception()).__str__().lower()


# ---------------------------------------------------------------------------
# Test: never with resolution succeeds
# ---------------------------------------------------------------------------

def test_never_with_resolution_succeeds(tmp_path: Path) -> None:
    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Out of scope suggestion",
            "--quadrant", "never",
            "--resolution", "Not applicable to this project's scale",
        ],
    )
    assert result.exit_code == 0, result.output
    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    assert "Out of scope suggestion" in content
    assert "Not applicable to this project" in content
    assert "CER-001" in content


# ---------------------------------------------------------------------------
# Test: IDs are sequential across quadrants
# ---------------------------------------------------------------------------

def test_ids_sequential_across_quadrants(tmp_path: Path) -> None:
    runner = CliRunner()

    calls = [
        ("now", "First finding"),
        ("later", "Second finding"),
        ("much_later", "Third finding"),
        ("now", "Fourth finding"),
        ("never", "Fifth finding", "Rejected because out of scope"),
    ]

    for args in calls:
        extra = []
        if len(args) == 3:
            extra = ["--resolution", args[2]]
        result = _invoke(
            runner,
            [
                "--project-dir", str(tmp_path),
                "--finding", args[1],
                "--quadrant", args[0],
            ] + extra,
        )
        assert result.exit_code == 0, result.output

    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    for expected_id in ["CER-001", "CER-002", "CER-003", "CER-004", "CER-005"]:
        assert expected_id in content, f"{expected_id} not found in backlog"


# ---------------------------------------------------------------------------
# Test: multiple calls accumulate entries correctly
# ---------------------------------------------------------------------------

def test_multiple_calls_accumulate(tmp_path: Path) -> None:
    runner = CliRunner()

    for i in range(1, 6):
        result = _invoke(
            runner,
            [
                "--project-dir", str(tmp_path),
                "--finding", f"Finding number {i}",
                "--quadrant", "later",
            ],
        )
        assert result.exit_code == 0, result.output

    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    for i in range(1, 6):
        assert f"Finding number {i}" in content

    entries = _parse_entries_from_backlog(content)
    assert len(entries) == 5
    ids = [e["id"] for e in entries]
    assert ids == ["CER-001", "CER-002", "CER-003", "CER-004", "CER-005"]


# ---------------------------------------------------------------------------
# Test: graceful error when backlog.md has unexpected content
# ---------------------------------------------------------------------------

def test_graceful_on_unexpected_content(tmp_path: Path) -> None:
    """If backlog.md exists but has garbage content, append_finding raises ClickException."""
    backlog = _backlog_path(tmp_path)
    backlog.parent.mkdir(parents=True, exist_ok=True)
    # Write completely unparseable binary-like content
    backlog.write_text("<<< MERGE CONFLICT >>>\n<<<<<<<\nfoo\n=======\nbar\n>>>>>>>", encoding="utf-8")

    # Parsing garbage should not crash — it should return empty list (no table rows matched)
    # and then append works fine. The "graceful error" test verifies we don't raise an
    # unexpected exception (i.e., no crash).
    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Finding after corruption",
            "--quadrant", "now",
        ],
    )
    # Should either succeed (with CER-001 appended) or exit with a friendly error
    # but NEVER raise an unhandled exception
    assert result.exit_code in (0, 1)
    if result.exit_code == 0:
        content = backlog.read_text(encoding="utf-8")
        assert "Finding after corruption" in content


# ---------------------------------------------------------------------------
# Test: phase option is stored and rendered
# ---------------------------------------------------------------------------

def test_phase_option_stored(tmp_path: Path) -> None:
    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Phase-tagged finding",
            "--quadrant", "later",
            "--phase", "7",
        ],
    )
    assert result.exit_code == 0, result.output
    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    assert "Phase-tagged finding" in content
    # Phase 7 should appear in the row
    assert "7" in content


# ---------------------------------------------------------------------------
# Test: reviewer option stored as source
# ---------------------------------------------------------------------------

def test_reviewer_stored_as_source(tmp_path: Path) -> None:
    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Security finding",
            "--quadrant", "now",
            "--reviewer", "security-team",
        ],
    )
    assert result.exit_code == 0, result.output
    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    assert "security-team" in content


# ---------------------------------------------------------------------------
# Test: _next_cer_id logic
# ---------------------------------------------------------------------------

def test_next_cer_id_empty() -> None:
    assert _next_cer_id([]) == "CER-001"


def test_next_cer_id_existing() -> None:
    entries = [
        {"id": "CER-001", "finding": "a", "quadrant": "do_now"},
        {"id": "CER-003", "finding": "b", "quadrant": "do_later"},
    ]
    assert _next_cer_id(entries) == "CER-004"


# ---------------------------------------------------------------------------
# Test: CER IDs increment from existing entries on re-run
# ---------------------------------------------------------------------------

def test_cer_id_increments_from_existing(tmp_path: Path) -> None:
    """When backlog already contains CER-001 through CER-003, new entry gets CER-004."""
    runner = CliRunner()

    # Seed CER-001 through CER-003
    for i, finding in enumerate(["First", "Second", "Third"], start=1):
        result = _invoke(
            runner,
            ["--project-dir", str(tmp_path), "--finding", finding, "--quadrant", "now"],
        )
        assert result.exit_code == 0, result.output

    # Add a fourth entry — must be CER-004, not CER-001
    result = _invoke(
        runner,
        ["--project-dir", str(tmp_path), "--finding", "Fourth", "--quadrant", "later"],
    )
    assert result.exit_code == 0, result.output
    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    assert "CER-004" in content
    # CER-001 through CER-003 must still be present
    for expected in ["CER-001", "CER-002", "CER-003"]:
        assert expected in content


def test_cer_id_not_restarted_after_gap(tmp_path: Path) -> None:
    """When backlog has CER-001 and CER-003 (gap at CER-002), new entry gets CER-004."""
    runner = CliRunner()

    # Seed CER-001 and CER-003 directly via two calls, then simulate a gap
    # by building CER-001, CER-002, CER-003 and then manually removing CER-002's row
    # from the markdown so entries list has a gap.
    for finding in ("Alpha", "Beta", "Gamma"):
        result = _invoke(
            runner,
            ["--project-dir", str(tmp_path), "--finding", finding, "--quadrant", "now"],
        )
        assert result.exit_code == 0, result.output

    # Remove the CER-002 row from backlog.md to simulate a resolved/removed entry
    backlog = _backlog_path(tmp_path)
    original = backlog.read_text(encoding="utf-8")
    lines = [ln for ln in original.splitlines(keepends=True) if "CER-002" not in ln]
    backlog.write_text("".join(lines), encoding="utf-8")

    # Now add a new finding — should use max+1 = CER-004, not len+1 = CER-003
    result = _invoke(
        runner,
        ["--project-dir", str(tmp_path), "--finding", "Delta", "--quadrant", "later"],
    )
    assert result.exit_code == 0, result.output
    content = backlog.read_text(encoding="utf-8")
    assert "CER-004" in content
    assert "Delta" in content


# ---------------------------------------------------------------------------
# Test: project_name read from pairmode_context.json
# ---------------------------------------------------------------------------

def test_project_name_from_context_json(tmp_path: Path) -> None:
    """When .companion/pairmode_context.json has project_name, backlog header uses it."""
    import json

    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir(parents=True, exist_ok=True)
    context_file = companion_dir / "pairmode_context.json"
    context_file.write_text(
        json.dumps({"project_name": "MyAwesomeProject"}), encoding="utf-8"
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Auth bypass on admin route",
            "--quadrant", "now",
        ],
    )
    assert result.exit_code == 0, result.output

    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    assert "MyAwesomeProject" in content


# ---------------------------------------------------------------------------
# Test: project_name fallback when no context.json present
# ---------------------------------------------------------------------------

def test_project_name_fallback_no_context(tmp_path: Path) -> None:
    """When pairmode_context.json is absent, heading-parse fallback does not crash."""
    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Some finding without context file",
            "--quadrant", "later",
        ],
    )
    assert result.exit_code == 0, result.output

    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    assert "Some finding without context file" in content
    assert "CER-001" in content


# ---------------------------------------------------------------------------
# Test: project_name from .companion/pairmode_context.json (correct subdir)
# ---------------------------------------------------------------------------

def test_project_name_from_companion_subdir(tmp_path: Path) -> None:
    """project_name is read from .companion/pairmode_context.json (not project root)."""
    import json

    # Write context to the correct location (.companion/ subdir)
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir(parents=True, exist_ok=True)
    (companion_dir / "pairmode_context.json").write_text(
        json.dumps({"project_name": "CorrectPathProject"}), encoding="utf-8"
    )

    # Also ensure a stale file at the wrong (old) path does NOT take precedence
    (tmp_path / "pairmode_context.json").write_text(
        json.dumps({"project_name": "WrongPathProject"}), encoding="utf-8"
    )

    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Path verification finding",
            "--quadrant", "now",
        ],
    )
    assert result.exit_code == 0, result.output

    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    assert "CorrectPathProject" in content
    assert "WrongPathProject" not in content


# ---------------------------------------------------------------------------
# Test: pipe character in finding text is escaped in table cell
# ---------------------------------------------------------------------------

def test_pipe_in_finding_is_escaped(tmp_path: Path) -> None:
    """A literal | in a finding is escaped as \\| so the markdown table row is not broken."""
    runner = CliRunner()
    result = _invoke(
        runner,
        [
            "--project-dir", str(tmp_path),
            "--finding", "foo | bar",
            "--quadrant", "now",
        ],
    )
    assert result.exit_code == 0, result.output

    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    # Escaped form must be present
    assert r"foo \| bar" in content
    # Raw unescaped form must not appear inside a table cell (the heading may contain
    # project name; check only the CER row lines)
    for line in content.splitlines():
        if line.strip().startswith("| CER-"):
            assert "foo | bar" not in line, (
                f"Unescaped pipe found in table row: {line!r}"
            )


# ---------------------------------------------------------------------------
# Test: _escape_table_cell helper
# ---------------------------------------------------------------------------

def test_escape_table_cell_no_pipe() -> None:
    assert _escape_table_cell("no pipes here") == "no pipes here"


def test_escape_table_cell_single_pipe() -> None:
    assert _escape_table_cell("a | b") == r"a \| b"


def test_escape_table_cell_multiple_pipes() -> None:
    assert _escape_table_cell("a | b | c") == r"a \| b \| c"


# ---------------------------------------------------------------------------
# Tests: depth guard
# ---------------------------------------------------------------------------

def test_depth_guard_root_exits_nonzero() -> None:
    """--project-dir / is too shallow: must exit non-zero with error message."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project-dir", "/", "--finding", "x", "--quadrant", "now"],
        catch_exceptions=False,
    )
    assert result.exit_code != 0
    assert "too shallow" in (result.output + (result.stderr if hasattr(result, "stderr") else "")).lower() or \
           "too shallow" in result.output.lower()


def test_depth_guard_tmp_exits_nonzero() -> None:
    """--project-dir /tmp is only 2 parts deep: must exit non-zero."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--project-dir", "/tmp", "--finding", "x", "--quadrant", "now"],
        catch_exceptions=False,
    )
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# Tests: malformed-markdown warning (INFRA-010)
# ---------------------------------------------------------------------------

_MALFORMED_BACKLOG = """\
# Some Project — CER Backlog

This file has more than five lines but contains no pipe-delimited table rows.
It uses freeform prose instead of the expected markdown table format.
There are no CER IDs here at all.
Just a heading and some paragraphs.
No tables to parse.
Nothing that matches the row regex.
End of file.
"""


def test_malformed_backlog_emits_warning(tmp_path: Path) -> None:
    """backlog.md with 10+ lines but no table rows → warning printed to stderr; process continues."""
    backlog = _backlog_path(tmp_path)
    backlog.parent.mkdir(parents=True, exist_ok=True)
    backlog.write_text(_MALFORMED_BACKLOG, encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Finding after malformed backlog",
            "--quadrant", "now",
        ],
        catch_exceptions=False,
    )

    # Process must continue without error
    assert result.exit_code == 0, result.output
    # Warning must appear in output (Click merges stderr into output by default)
    assert "Warning: backlog.md exists but no table rows were parsed" in result.output
    # Finding must be written
    content = backlog.read_text(encoding="utf-8")
    assert "Finding after malformed backlog" in content


def test_normal_backlog_no_warning(tmp_path: Path) -> None:
    """backlog.md with CER-001 and CER-002 → no warning; CER-003 assigned to new finding."""
    runner = CliRunner()

    # Seed two entries
    for finding in ("First finding", "Second finding"):
        result = runner.invoke(
            cli,
            [
                "--project-dir", str(tmp_path),
                "--finding", finding,
                "--quadrant", "now",
            ],
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output

    # Now add a third entry
    result = runner.invoke(
        cli,
        [
            "--project-dir", str(tmp_path),
            "--finding", "Third finding",
            "--quadrant", "now",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output
    # No warning should be emitted for a well-formed backlog
    assert "Warning: backlog.md exists but no table rows were parsed" not in result.output

    content = _backlog_path(tmp_path).read_text(encoding="utf-8")
    assert "CER-001" in content
    assert "CER-002" in content
    assert "CER-003" in content
    assert "Third finding" in content
