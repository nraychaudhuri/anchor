"""
test_skill_md.py — Documentation accuracy test for skills/pairmode/SKILL.md.

For each --flag mentioned in CLI invocation blocks in SKILL.md for
phase_new.py, cer.py, and bootstrap.py, verifies that the corresponding
script actually defines that option.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SKILL_MD = Path(__file__).parent.parent.parent / "skills" / "pairmode" / "SKILL.md"
SCRIPTS_DIR = Path(__file__).parent.parent.parent / "skills" / "pairmode" / "scripts"

SCRIPT_MAP = {
    "phase_new.py": SCRIPTS_DIR / "phase_new.py",
    "cer.py": SCRIPTS_DIR / "cer.py",
    "bootstrap.py": SCRIPTS_DIR / "bootstrap.py",
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Matches a CLI invocation block that references a specific script.
# We look for lines like:  uv run python ".../<script>.py"  followed by flags.
_SCRIPT_BLOCK_RE = re.compile(
    r'uv run python[^\n]*?/scripts/(?P<script>\w+\.py)[^\n]*\n'
    r'(?P<flags>(?:[^\n]+\n)*?)'
    r'(?=\n|\Z|```)',
    re.MULTILINE,
)

# Matches --flag-name patterns.
_FLAG_RE = re.compile(r"--([a-z][a-z0-9-]*)")

# Matches click option declarations: @click.option("--flag-name" ...)
_CLICK_OPTION_RE = re.compile(r'@click\.option\(\s*["\']--([a-z][a-z0-9-]+)["\']')


def _extract_flags_from_skill_md(script_name: str) -> set[str]:
    """Parse SKILL.md and extract all --flags used in invocation blocks for the given script."""
    text = SKILL_MD.read_text(encoding="utf-8")
    flags: set[str] = set()

    # Find all code blocks (``` ... ```) that mention the script
    code_blocks = re.findall(r"```(?:bash)?\n(.*?)```", text, re.DOTALL)
    for block in code_blocks:
        if script_name not in block:
            continue
        # Extract all --flags from this block
        for match in _FLAG_RE.finditer(block):
            flags.add(match.group(1))

    return flags


def _extract_documented_flags_from_skill_md(script_name: str) -> set[str]:
    """Extract --flags from the 'Flags:' or 'Optional flags:' bullet list for the given script.

    Looks for bullet points of the form:
      - `--flag-name ...` — description

    Only parses the flags list that immediately follows the CLI invocation block
    for the given script name, stopping at the next blank line after the list or
    the next **bold** heading.
    """
    text = SKILL_MD.read_text(encoding="utf-8")
    flags: set[str] = set()

    pos = text.find(script_name)
    if pos == -1:
        return flags

    # Find the start of the surrounding section (last ### before pos)
    section_start = text.rfind("###", 0, pos)
    if section_start == -1:
        section_start = 0

    # Find the next ### heading after section_start (exclusive of section_start)
    next_section_match = re.search(r"^###", text[section_start + 3:], re.MULTILINE)
    if next_section_match:
        section_end = section_start + 3 + next_section_match.start()
    else:
        section_end = len(text)

    section = text[section_start:section_end]

    # Find the "Flags:" or "Optional flags:" sub-section within this section.
    # Only parse flags listed in that sub-section (bullet list ending at blank line
    # or next bold heading).
    flags_block_match = re.search(
        r"(?:Optional flags|Flags):\s*\n((?:-\s+`--[^\n]+\n)+)",
        section,
    )
    if flags_block_match:
        for match in _FLAG_RE.finditer(flags_block_match.group(1)):
            flags.add(match.group(1))

    return flags


def _extract_click_options(script_path: Path) -> set[str]:
    """Extract all click option names from a script file."""
    text = script_path.read_text(encoding="utf-8")
    return {m.group(1) for m in _CLICK_OPTION_RE.finditer(text)}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSkillMdExists:
    def test_skill_md_exists(self):
        assert SKILL_MD.exists(), f"SKILL.md not found at {SKILL_MD}"

    def test_scripts_exist(self):
        for name, path in SCRIPT_MAP.items():
            assert path.exists(), f"Script not found: {path}"


class TestBootstrapFlags:
    """All --flags documented in SKILL.md for bootstrap.py must exist in the script."""

    SCRIPT = "bootstrap.py"

    def test_invocation_block_flags_exist_in_script(self):
        """Flags used in code blocks referencing bootstrap.py must be defined in the script."""
        documented = _extract_flags_from_skill_md(self.SCRIPT)
        defined = _extract_click_options(SCRIPT_MAP[self.SCRIPT])
        missing = documented - defined
        assert not missing, (
            f"Flags documented in SKILL.md code blocks for {self.SCRIPT} "
            f"but not defined in script: {sorted(missing)}"
        )

    def test_section_flags_exist_in_script(self):
        """Flags listed in the bootstrap section of SKILL.md must be defined in the script."""
        documented = _extract_documented_flags_from_skill_md(self.SCRIPT)
        defined = _extract_click_options(SCRIPT_MAP[self.SCRIPT])
        missing = documented - defined
        assert not missing, (
            f"Flags documented in SKILL.md flags section for {self.SCRIPT} "
            f"but not defined in script: {sorted(missing)}"
        )


class TestPhaseNewFlags:
    """All --flags documented in SKILL.md for phase_new.py must exist in the script."""

    SCRIPT = "phase_new.py"

    def test_invocation_block_flags_exist_in_script(self):
        documented = _extract_flags_from_skill_md(self.SCRIPT)
        defined = _extract_click_options(SCRIPT_MAP[self.SCRIPT])
        missing = documented - defined
        assert not missing, (
            f"Flags documented in SKILL.md code blocks for {self.SCRIPT} "
            f"but not defined in script: {sorted(missing)}"
        )

    def test_section_flags_exist_in_script(self):
        documented = _extract_documented_flags_from_skill_md(self.SCRIPT)
        defined = _extract_click_options(SCRIPT_MAP[self.SCRIPT])
        missing = documented - defined
        assert not missing, (
            f"Flags documented in SKILL.md flags section for {self.SCRIPT} "
            f"but not defined in script: {sorted(missing)}"
        )

    def test_dry_run_flag_present_in_script(self):
        """phase_new.py must define --dry-run (added in Story 8.3)."""
        defined = _extract_click_options(SCRIPT_MAP[self.SCRIPT])
        assert "dry-run" in defined, "--dry-run not found in phase_new.py click options"

    def test_dry_run_documented_in_skill_md(self):
        """SKILL.md must document --dry-run for phase_new."""
        section_flags = _extract_documented_flags_from_skill_md(self.SCRIPT)
        assert "dry-run" in section_flags, "--dry-run not found in SKILL.md phase-new section"


class TestCerFlags:
    """All --flags documented in SKILL.md for cer.py must exist in the script."""

    SCRIPT = "cer.py"

    def test_invocation_block_flags_exist_in_script(self):
        documented = _extract_flags_from_skill_md(self.SCRIPT)
        defined = _extract_click_options(SCRIPT_MAP[self.SCRIPT])
        missing = documented - defined
        assert not missing, (
            f"Flags documented in SKILL.md code blocks for {self.SCRIPT} "
            f"but not defined in script: {sorted(missing)}"
        )

    def test_section_flags_exist_in_script(self):
        documented = _extract_documented_flags_from_skill_md(self.SCRIPT)
        defined = _extract_click_options(SCRIPT_MAP[self.SCRIPT])
        missing = documented - defined
        assert not missing, (
            f"Flags documented in SKILL.md flags section for {self.SCRIPT} "
            f"but not defined in script: {sorted(missing)}"
        )

    def test_reviewer_flag_not_source(self):
        """cer.py must use --reviewer, not --source (fixed in Story 8.2)."""
        defined = _extract_click_options(SCRIPT_MAP[self.SCRIPT])
        assert "reviewer" in defined, "--reviewer not found in cer.py click options"
        assert "source" not in defined, (
            "--source found in cer.py: should be --reviewer after Story 8.2 fix"
        )

    def test_reviewer_documented_not_source(self):
        """SKILL.md must document --reviewer for cer, not --source."""
        text = SKILL_MD.read_text(encoding="utf-8")
        # Find the cer section
        cer_pos = text.find("/scripts/cer.py")
        assert cer_pos != -1, "cer.py invocation not found in SKILL.md"
        section_end = text.find("\n---\n", cer_pos)
        section = text[cer_pos:section_end] if section_end != -1 else text[cer_pos:]
        assert "--reviewer" in section, "--reviewer not documented in cer section of SKILL.md"


class TestBootstrapOutputs:
    """Bootstrap Outputs section must list actual files, not the old phase-prompts.md."""

    def test_phase_prompts_not_in_outputs(self):
        """docs/phase-prompts.md must not appear in the Bootstrap Outputs list."""
        text = SKILL_MD.read_text(encoding="utf-8")
        # Find the outputs section for bootstrap
        bootstrap_pos = text.find("### `/anchor:pairmode bootstrap`")
        assert bootstrap_pos != -1
        # Find the next ### section
        next_section = text.find("\n### ", bootstrap_pos + 1)
        bootstrap_section = text[bootstrap_pos:next_section] if next_section != -1 else text[bootstrap_pos:]
        assert "phase-prompts.md" not in bootstrap_section, (
            "docs/phase-prompts.md must not appear in bootstrap Outputs section — "
            "it is no longer written by bootstrap"
        )

    def test_actual_output_files_documented(self):
        """Bootstrap Outputs must include the actual files written."""
        text = SKILL_MD.read_text(encoding="utf-8")
        bootstrap_pos = text.find("### `/anchor:pairmode bootstrap`")
        next_section = text.find("\n### ", bootstrap_pos + 1)
        section = text[bootstrap_pos:next_section] if next_section != -1 else text[bootstrap_pos:]

        expected_files = [
            "CLAUDE.md",
            "CLAUDE.build.md",
            "docs/brief.md",
            "docs/architecture.md",
            "docs/checkpoints.md",
            "docs/phases/index.md",
            "docs/phases/phase-1.md",
            "docs/cer/backlog.md",
            ".claude/settings.json",
            ".companion/state.json",
        ]
        for f in expected_files:
            assert f in section, f"Expected output file '{f}' not found in bootstrap Outputs section"

    def test_force_agents_caveat_documented(self):
        """Bootstrap Outputs must note that agent files are skipped unless --force-agents is passed."""
        text = SKILL_MD.read_text(encoding="utf-8")
        bootstrap_pos = text.find("### `/anchor:pairmode bootstrap`")
        next_section = text.find("\n### ", bootstrap_pos + 1)
        section = text[bootstrap_pos:next_section] if next_section != -1 else text[bootstrap_pos:]
        assert "--force-agents" in section, (
            "Bootstrap section must mention --force-agents in context of agent file ownership"
        )


class TestDispatcherNotes:
    """phase-new and cer sections must include a CLI-only dispatcher note."""

    def test_phase_new_has_dispatcher_note(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        phase_new_pos = text.find("### `/anchor:pairmode phase-new`")
        assert phase_new_pos != -1
        next_section = text.find("\n### ", phase_new_pos + 1)
        section = text[phase_new_pos:next_section] if next_section != -1 else text[phase_new_pos:]
        assert "phase_new.py" in section, "phase-new section must include CLI invocation with phase_new.py"
        # Check the note appears before the "When to use" block
        note_pos = section.find("Note")
        when_pos = section.find("**When to use:**")
        assert note_pos != -1 and note_pos < when_pos, (
            "Dispatcher note must appear before 'When to use:' in phase-new section"
        )

    def test_cer_has_dispatcher_note(self):
        text = SKILL_MD.read_text(encoding="utf-8")
        cer_pos = text.find("### `/anchor:pairmode cer`")
        assert cer_pos != -1
        next_section = text.find("\n### ", cer_pos + 1)
        section = text[cer_pos:next_section] if next_section != -1 else text[cer_pos:]
        assert "cer.py" in section, "cer section must include CLI invocation with cer.py"
        note_pos = section.find("Note")
        when_pos = section.find("**When to use:**")
        assert note_pos != -1 and note_pos < when_pos, (
            "Dispatcher note must appear before 'When to use:' in cer section"
        )
