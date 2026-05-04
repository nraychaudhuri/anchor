"""
test_e2e_roundtrip.py — End-to-end smoke test for the full pairmode adoption flow.

Exercises: bootstrap → audit → drift → audit → sync → audit → context_missing.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from click.testing import CliRunner

from skills.pairmode.scripts.bootstrap import bootstrap
from skills.pairmode.scripts.audit import audit_project, format_audit_output
from skills.pairmode.scripts.sync import sync_project, SyncResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run_bootstrap(project_dir: Path) -> None:
    """Invoke bootstrap CLI with non-interactive defaults."""
    runner = CliRunner()
    result = runner.invoke(
        bootstrap,
        [
            "--project-dir", str(project_dir),
            "--project-name", "e2eproject",
            "--stack", "Python / pytest",
            "--build-command", "uv run pytest",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, f"bootstrap failed:\n{result.output}"


def _remove_first_h2_section(text: str) -> tuple[str, str]:
    """Remove the first ## section from markdown text.

    Returns (modified_text, removed_heading) where removed_heading is the
    heading text that was stripped (e.g. '## Session modes').
    """
    lines = text.splitlines(keepends=True)
    # Find first ## heading
    first_h2_idx = None
    for i, line in enumerate(lines):
        if line.startswith("## "):
            first_h2_idx = i
            break

    if first_h2_idx is None:
        raise ValueError("No ## heading found in text")

    removed_heading = lines[first_h2_idx].rstrip("\n")

    # Find the next ## heading (or end of file)
    next_h2_idx = None
    for i in range(first_h2_idx + 1, len(lines)):
        if lines[i].startswith("## "):
            next_h2_idx = i
            break

    # Remove the section (heading + body)
    if next_h2_idx is not None:
        new_lines = lines[:first_h2_idx] + lines[next_h2_idx:]
    else:
        new_lines = lines[:first_h2_idx]

    return "".join(new_lines), removed_heading


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------

class TestFullAdoptionJourney:
    """End-to-end test of the pairmode adoption lifecycle."""

    # -----------------------------------------------------------------------
    # Step 1: Bootstrap
    # -----------------------------------------------------------------------

    def test_step1_bootstrap_creates_scaffold_files(self, tmp_path: Path) -> None:
        """Bootstrap creates the required scaffold files."""
        _run_bootstrap(tmp_path)

        assert (tmp_path / "CLAUDE.md").exists(), "CLAUDE.md must exist after bootstrap"
        assert (tmp_path / "CLAUDE.build.md").exists(), "CLAUDE.build.md must exist after bootstrap"
        assert (tmp_path / ".claude" / "agents" / "builder.md").exists(), (
            ".claude/agents/builder.md must exist after bootstrap"
        )
        assert (tmp_path / ".claude" / "settings.json").exists(), (
            ".claude/settings.json must exist after bootstrap"
        )

    def test_step1_bootstrap_creates_pairmode_context(self, tmp_path: Path) -> None:
        """Bootstrap writes .companion/pairmode_context.json."""
        _run_bootstrap(tmp_path)
        assert (tmp_path / ".companion" / "pairmode_context.json").exists(), (
            ".companion/pairmode_context.json must exist after bootstrap"
        )

    def test_step1_bootstrap_state_json_has_pairmode_version(self, tmp_path: Path) -> None:
        """Bootstrap writes pairmode_version into .companion/state.json."""
        _run_bootstrap(tmp_path)
        state_path = tmp_path / ".companion" / "state.json"
        assert state_path.exists(), ".companion/state.json must exist after bootstrap"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        assert "pairmode_version" in state, "state.json must contain pairmode_version"

    def test_step1_bootstrap_creates_deny_rationale(self, tmp_path: Path) -> None:
        """Bootstrap writes .claude/settings.deny-rationale.json."""
        _run_bootstrap(tmp_path)
        assert (tmp_path / ".claude" / "settings.deny-rationale.json").exists(), (
            ".claude/settings.deny-rationale.json must exist after bootstrap"
        )

    # -----------------------------------------------------------------------
    # Step 2: Audit immediately after bootstrap — expect clean result
    # -----------------------------------------------------------------------

    def test_step2_audit_after_bootstrap_is_clean(self, tmp_path: Path) -> None:
        """Audit immediately after bootstrap should report no missing sections and no
        non-stale-placeholder inconsistent sections.

        Note: STALE PLACEHOLDER findings for scaffold files (docs/brief.md etc.) are expected
        when --what and --why are not passed to bootstrap — they signal unfilled templates,
        not a structural drift from canonical. They are excluded from this assertion.
        """
        _run_bootstrap(tmp_path)

        result = audit_project(tmp_path)

        assert result.missing == [], (
            f"Expected no missing sections after bootstrap, got: {result.missing}"
        )
        non_stale_inconsistent = [
            i for i in result.inconsistent if "STALE PLACEHOLDER" not in i.description
        ]
        assert non_stale_inconsistent == [], (
            f"Expected no non-stale INCONSISTENT sections after bootstrap, "
            f"got: {non_stale_inconsistent}"
        )

    def test_step2_audit_after_bootstrap_context_not_missing(self, tmp_path: Path) -> None:
        """Audit after bootstrap should not report context_missing."""
        _run_bootstrap(tmp_path)
        result = audit_project(tmp_path)
        assert result.context_missing is False, (
            "context_missing should be False after bootstrap wrote pairmode_context.json"
        )

    # -----------------------------------------------------------------------
    # Step 3: Simulate drift — delete one ## section from CLAUDE.md
    # -----------------------------------------------------------------------

    def test_step3_audit_detects_missing_section(self, tmp_path: Path) -> None:
        """After removing a ## section from CLAUDE.md, audit reports it as missing."""
        _run_bootstrap(tmp_path)

        claude_md = tmp_path / "CLAUDE.md"
        original_text = claude_md.read_text(encoding="utf-8")
        drifted_text, removed_heading = _remove_first_h2_section(original_text)
        claude_md.write_text(drifted_text, encoding="utf-8")

        result = audit_project(tmp_path)

        # The removed section should appear in result.missing
        missing_files = {item.file for item in result.missing}
        assert "CLAUDE.md" in missing_files, (
            f"Expected CLAUDE.md to have missing sections after drift, but missing set is: "
            f"{[item.section for item in result.missing]}"
        )

    def test_step3_audit_after_drift_context_not_missing(self, tmp_path: Path) -> None:
        """Even after drift, context_missing should remain False (context file untouched)."""
        _run_bootstrap(tmp_path)

        claude_md = tmp_path / "CLAUDE.md"
        text, _ = _remove_first_h2_section(claude_md.read_text(encoding="utf-8"))
        claude_md.write_text(text, encoding="utf-8")

        result = audit_project(tmp_path)
        assert result.context_missing is False

    # -----------------------------------------------------------------------
    # Step 4: Sync — apply the drift
    # -----------------------------------------------------------------------

    def test_step4_sync_applied_is_non_empty(self, tmp_path: Path) -> None:
        """sync_project should apply at least one change after drift."""
        _run_bootstrap(tmp_path)

        claude_md = tmp_path / "CLAUDE.md"
        text, _ = _remove_first_h2_section(claude_md.read_text(encoding="utf-8"))
        claude_md.write_text(text, encoding="utf-8")

        sync_result = sync_project(tmp_path, yes=True)

        assert sync_result.applied, (
            "SyncResult.applied should be non-empty after applying drift"
        )

    def test_step4_sync_restores_removed_heading(self, tmp_path: Path) -> None:
        """After sync, the removed section heading text should appear in CLAUDE.md again.

        sync.py reconstructs headers from normalised keys (lowercase), so we check
        case-insensitively that the heading words are present in the file after sync.
        """
        _run_bootstrap(tmp_path)

        claude_md = tmp_path / "CLAUDE.md"
        original_text = claude_md.read_text(encoding="utf-8")
        drifted_text, removed_heading = _remove_first_h2_section(original_text)
        claude_md.write_text(drifted_text, encoding="utf-8")

        # Verify heading is absent before sync
        heading_words = removed_heading.lstrip("# ").strip()
        assert heading_words.lower() not in claude_md.read_text(encoding="utf-8").lower(), (
            "The removed heading should not be present before sync"
        )

        sync_project(tmp_path, yes=True)

        restored_text = claude_md.read_text(encoding="utf-8")
        # The heading text should be back (sync writes the normalised lowercase key as header)
        assert heading_words.lower() in restored_text.lower(), (
            f"Expected heading '{heading_words}' (case-insensitive) to be restored in "
            f"CLAUDE.md after sync"
        )

    # -----------------------------------------------------------------------
    # Step 5: Post-sync audit — expect clean again
    # -----------------------------------------------------------------------

    def test_step5_audit_after_sync_is_clean(self, tmp_path: Path) -> None:
        """After sync, a fresh audit should report no missing or inconsistent sections."""
        _run_bootstrap(tmp_path)

        claude_md = tmp_path / "CLAUDE.md"
        text, _ = _remove_first_h2_section(claude_md.read_text(encoding="utf-8"))
        claude_md.write_text(text, encoding="utf-8")

        sync_project(tmp_path, yes=True)

        result = audit_project(tmp_path)

        assert result.missing == [], (
            f"Expected no missing sections after sync, got: "
            f"{[(item.file, item.section) for item in result.missing]}"
        )
        non_stale_inconsistent = [
            i for i in result.inconsistent if "STALE PLACEHOLDER" not in i.description
        ]
        assert non_stale_inconsistent == [], (
            f"Expected no non-stale INCONSISTENT sections after sync, "
            f"got: {[(i.file, i.section) for i in non_stale_inconsistent]}"
        )

    # -----------------------------------------------------------------------
    # Step 6: Audit without context file — expect L001 behavior
    # -----------------------------------------------------------------------

    def test_step6_no_context_sets_context_missing_true(self, tmp_path: Path) -> None:
        """Deleting pairmode_context.json causes audit to report context_missing=True."""
        _run_bootstrap(tmp_path)

        context_path = tmp_path / ".companion" / "pairmode_context.json"
        context_path.unlink()
        assert not context_path.exists()

        result = audit_project(tmp_path)
        assert result.context_missing is True, (
            "context_missing should be True when pairmode_context.json is deleted"
        )

    def test_step6_no_context_inconsistent_canonical_files_suppressed(self, tmp_path: Path) -> None:
        """When context_missing, INCONSISTENT findings for canonical files (CLAUDE.md etc.)
        should be suppressed. STALE PLACEHOLDER findings for scaffold files may still appear
        since they read the project file body directly without needing the context."""
        _run_bootstrap(tmp_path)

        (tmp_path / ".companion" / "pairmode_context.json").unlink()

        result = audit_project(tmp_path)
        # All inconsistent items should be STALE PLACEHOLDER (from scaffold files)
        # — no regular body-diff INCONSISTENT for canonical files
        non_stale = [i for i in result.inconsistent if "STALE PLACEHOLDER" not in i.description]
        assert non_stale == [], (
            "Non-stale INCONSISTENT items should be suppressed when context file is absent; "
            f"got: {non_stale}"
        )

    def test_step6_no_context_format_output_contains_warning(self, tmp_path: Path) -> None:
        """format_audit_output should mention missing context when context_missing is True."""
        _run_bootstrap(tmp_path)

        (tmp_path / ".companion" / "pairmode_context.json").unlink()

        result = audit_project(tmp_path)
        output = format_audit_output(result)

        assert "No pairmode_context.json found" in output, (
            f"Expected 'No pairmode_context.json found' in audit output, got:\n{output}"
        )
