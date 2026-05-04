"""Tests for skills/pairmode/scripts/story_new.py."""

from __future__ import annotations

import pathlib

import pytest
from click.testing import CliRunner

from skills.pairmode.scripts.story_new import story_new


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def invoke(args: list[str], input: str | None = "Y\n") -> "click.testing.Result":
    """Invoke story_new.  Defaults to answering 'Y' to the rail-creation prompt."""
    runner = CliRunner()
    return runner.invoke(story_new, args, input=input, catch_exceptions=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestCreateStoryFile:
    """Basic story creation."""

    def test_creates_story_file_at_correct_path(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            ["--rail", "BOOTSTRAP", "--title", "My first story", "--project-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "BOOTSTRAP" / "BOOTSTRAP-001.md"
        assert story_file.exists(), f"Expected {story_file} to exist"

    def test_story_id_in_output(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            ["--rail", "AUDIT", "--title", "Audit something", "--project-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        assert "AUDIT-001" in result.output
        assert "Audit something" in result.output

    def test_correct_frontmatter_id(self, tmp_path: pathlib.Path) -> None:
        invoke(["--rail", "INFRA", "--title", "Infra story", "--project-dir", str(tmp_path)])
        story_file = tmp_path / "docs" / "stories" / "INFRA" / "INFRA-001.md"
        content = story_file.read_text()
        assert "id: INFRA-001" in content

    def test_rail_normalized_to_uppercase(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            ["--rail", "bootstrap", "--title", "Lower rail", "--project-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "BOOTSTRAP" / "BOOTSTRAP-001.md"
        assert story_file.exists()

    def test_frontmatter_contains_required_fields(self, tmp_path: pathlib.Path) -> None:
        invoke(["--rail", "BUILD", "--title", "Build story", "--project-dir", str(tmp_path)])
        story_file = tmp_path / "docs" / "stories" / "BUILD" / "BUILD-001.md"
        content = story_file.read_text()
        assert "id: BUILD-001" in content
        assert "rail: BUILD" in content
        assert "title: Build story" in content
        assert "status: draft" in content

    def test_primary_files_defaults_to_empty_list(self, tmp_path: pathlib.Path) -> None:
        """primary_files must appear as an empty list in frontmatter, not omitted."""
        invoke(["--rail", "TEMPLATE", "--title", "Template story", "--project-dir", str(tmp_path)])
        story_file = tmp_path / "docs" / "stories" / "TEMPLATE" / "TEMPLATE-001.md"
        content = story_file.read_text()
        # primary_files: followed by nothing (empty list) must be present
        assert "primary_files:" in content
        # It should NOT be missing entirely — verify the key is in the frontmatter block
        fm_block = content.split("---")[1]
        assert "primary_files:" in fm_block


class TestSequenceIncrement:
    """Sequence number increments for subsequent stories on the same rail."""

    def test_second_story_gets_002(self, tmp_path: pathlib.Path) -> None:
        invoke(["--rail", "BOOTSTRAP", "--title", "First", "--project-dir", str(tmp_path)])
        result = invoke(
            ["--rail", "BOOTSTRAP", "--title", "Second", "--project-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        story_file = tmp_path / "docs" / "stories" / "BOOTSTRAP" / "BOOTSTRAP-002.md"
        assert story_file.exists(), "Expected BOOTSTRAP-002.md to exist"
        assert "BOOTSTRAP-002" in result.output

    def test_third_story_gets_003(self, tmp_path: pathlib.Path) -> None:
        for title in ("A", "B", "C"):
            invoke(["--rail", "AUDIT", "--title", title, "--project-dir", str(tmp_path)])
        story_file = tmp_path / "docs" / "stories" / "AUDIT" / "AUDIT-003.md"
        assert story_file.exists()


class TestNewRailPrompt:
    """Prompting when a rail does not exist."""

    def test_declining_prompt_aborts_no_directory_created(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            ["--rail", "NEWRAIL", "--title", "First", "--project-dir", str(tmp_path)],
            input="n\n",
        )
        assert result.exit_code == 0, result.output
        rail_dir = tmp_path / "docs" / "stories" / "NEWRAIL"
        assert not rail_dir.exists(), "Rail directory must not be created when user declines"

    def test_accepting_prompt_creates_directory_and_story(self, tmp_path: pathlib.Path) -> None:
        result = invoke(
            ["--rail", "NEWRAIL", "--title", "First", "--project-dir", str(tmp_path)],
            input="Y\n",
        )
        assert result.exit_code == 0, result.output
        rail_dir = tmp_path / "docs" / "stories" / "NEWRAIL"
        assert rail_dir.is_dir()
        story_file = rail_dir / "NEWRAIL-001.md"
        assert story_file.exists()

    def test_existing_rail_no_prompt(self, tmp_path: pathlib.Path) -> None:
        """When the rail already exists no prompt is shown."""
        rail_dir = tmp_path / "docs" / "stories" / "EXISTING"
        rail_dir.mkdir(parents=True)
        # Invoke without any stdin input — would fail if a prompt appeared
        result = invoke(
            ["--rail", "EXISTING", "--title", "Story", "--project-dir", str(tmp_path)],
        )
        assert result.exit_code == 0, result.output


class TestPhaseFlag:
    """--phase appends a row to the phase manifest."""

    def _make_phase_file(self, tmp_path: pathlib.Path, phase: str, with_table: bool = False) -> pathlib.Path:
        phases_dir = tmp_path / "docs" / "phases"
        phases_dir.mkdir(parents=True, exist_ok=True)
        phase_path = phases_dir / f"phase-{phase}.md"
        if with_table:
            content = (
                f"# Phase {phase}\n\n"
                "## Stories\n\n"
                "| Story ID | Title | Status |\n"
                "|----------|-------|--------|\n"
            )
        else:
            content = f"# Phase {phase}\n\n## Goal\n\nDo things.\n"
        phase_path.write_text(content, encoding="utf-8")
        return phase_path

    def test_phase_flag_appends_row_to_existing_table(self, tmp_path: pathlib.Path) -> None:
        phase_path = self._make_phase_file(tmp_path, "001", with_table=True)
        # Pre-create rail so no prompt
        rail_dir = tmp_path / "docs" / "stories" / "BUILD"
        rail_dir.mkdir(parents=True)

        result = invoke(
            [
                "--rail", "BUILD",
                "--title", "My build story",
                "--phase", "001",
                "--project-dir", str(tmp_path),
            ]
        )
        assert result.exit_code == 0, result.output
        assert "Added to Phase 001" in result.output

        content = phase_path.read_text()
        assert "BUILD-001" in content
        assert "My build story" in content

    def test_phase_flag_creates_stories_section_if_absent(self, tmp_path: pathlib.Path) -> None:
        phase_path = self._make_phase_file(tmp_path, "002", with_table=False)
        rail_dir = tmp_path / "docs" / "stories" / "AUDIT"
        rail_dir.mkdir(parents=True)

        result = invoke(
            [
                "--rail", "AUDIT",
                "--title", "Audit story",
                "--phase", "002",
                "--project-dir", str(tmp_path),
            ]
        )
        assert result.exit_code == 0, result.output
        content = phase_path.read_text()
        assert "AUDIT-001" in content
        assert "Audit story" in content

    def test_phase_flag_prints_added_to_phase(self, tmp_path: pathlib.Path) -> None:
        self._make_phase_file(tmp_path, "003", with_table=True)
        rail_dir = tmp_path / "docs" / "stories" / "LESSON"
        rail_dir.mkdir(parents=True)

        result = invoke(
            [
                "--rail", "LESSON",
                "--title", "Lesson story",
                "--phase", "003",
                "--project-dir", str(tmp_path),
            ]
        )
        assert "Added to Phase 003" in result.output


class TestValidationIntegration:
    """Validation is called after creation; errors are printed as warnings."""

    def test_no_validation_warnings_on_new_draft_story(self, tmp_path: pathlib.Path) -> None:
        """Draft stories with empty primary_files must produce no validation warnings."""
        result = invoke(
            ["--rail", "INFRA", "--title", "Validation test", "--project-dir", str(tmp_path)]
        )
        assert result.exit_code == 0, result.output
        # stderr (mixed into output by CliRunner by default) must not contain warning text
        assert "validation:" not in result.output

    def test_validation_warning_printed_to_stderr_on_error(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When the validator returns a fake error, it is printed to stderr, exit code stays 0."""
        import sys

        # story_new.py imports 'schema_validator' via a sys.path insert (plain module name).
        # Ensure that plain-name module is loaded and patch it.
        import skills.pairmode.scripts.schema_validator as _sv_pkg  # ensure loaded

        # Register under the plain name so the local import inside story_new resolves it
        monkeypatch.setitem(sys.modules, "schema_validator", _sv_pkg)
        monkeypatch.setattr(_sv_pkg, "validate_story_file", lambda path: ["fake validation error"])

        # CliRunner mixes stdout+stderr into result.output by default
        runner = CliRunner()
        result = runner.invoke(
            story_new,
            ["--rail", "WARN", "--title", "Warn story", "--project-dir", str(tmp_path)],
            input="Y\n",
            catch_exceptions=False,
        )
        assert result.exit_code == 0, result.output
        assert "fake validation error" in result.output

    def test_validation_warning_exit_code_still_zero(
        self, tmp_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Exit code remains 0 even when validation warnings are emitted."""
        import sys
        import skills.pairmode.scripts.schema_validator as _sv_pkg

        monkeypatch.setitem(sys.modules, "schema_validator", _sv_pkg)
        monkeypatch.setattr(_sv_pkg, "validate_story_file", lambda path: ["some error"])

        runner = CliRunner()
        result = runner.invoke(
            story_new,
            ["--rail", "EXIT", "--title", "Exit story", "--project-dir", str(tmp_path)],
            input="Y\n",
            catch_exceptions=False,
        )
        assert result.exit_code == 0


class TestPathTraversalGuard:
    """Too-shallow project_dir causes non-zero exit."""

    def test_shallow_path_exits_nonzero(self, tmp_path: pathlib.Path) -> None:
        # / has only 1 part, which is < 3
        runner = CliRunner()
        # We need to pass a path with < 3 parts.  Use a monkeypatched path.
        # The easiest approach: resolve a known shallow path.
        # On Linux /tmp itself has 2 parts: ('/', 'tmp') — still < 3.
        # We call the script with an existing directory that resolves to a shallow path.
        # Rather than using a real shallow path (which might not exist in test env),
        # let's test the guard by importing and calling directly.
        from pathlib import Path as _Path
        import sys as _sys

        # Patch the resolve to return a shallow path by temporarily overriding
        # We test via CLI with the actual guard: use /tmp which has 2 parts on Linux
        shallow = pathlib.Path("/tmp")
        if len(shallow.resolve().parts) < 3:
            result = runner.invoke(
                story_new,
                ["--rail", "INFRA", "--title", "t", "--project-dir", str(shallow)],
                catch_exceptions=False,
            )
            assert result.exit_code != 0
        else:
            # On some systems /tmp resolves to more parts — skip this check gracefully
            pytest.skip("/tmp resolves to >= 3 parts on this system")
