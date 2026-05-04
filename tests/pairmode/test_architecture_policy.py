"""Tests for Story 8.7: per-phase file policy and Phase 8 migration."""
from pathlib import Path

# Repo root is two levels up from tests/pairmode/
REPO_ROOT = Path(__file__).parent.parent.parent


def test_phase8_file_exists():
    """docs/phases/phase-8.md must exist in the repo."""
    phase8 = REPO_ROOT / "docs" / "phases" / "phase-8.md"
    assert phase8.exists(), f"Expected {phase8} to exist"


def test_architecture_md_has_phase_documentation_policy():
    """docs/architecture.md must contain the Phase documentation policy section."""
    arch_md = REPO_ROOT / "docs" / "architecture.md"
    content = arch_md.read_text()
    assert "Phase documentation policy" in content, (
        "docs/architecture.md must contain 'Phase documentation policy'"
    )


def test_phases_index_contains_phase8():
    """docs/phases/index.md must reference phase-8."""
    index_md = REPO_ROOT / "docs" / "phases" / "index.md"
    content = index_md.read_text()
    assert "phase-8" in content, (
        "docs/phases/index.md must contain a row referencing 'phase-8'"
    )


def test_phase_prompts_phase8_is_redirect():
    """docs/phase-prompts.md Phase 8 section must be a redirect stub, not the full spec."""
    phase_prompts = REPO_ROOT / "docs" / "phase-prompts.md"
    content = phase_prompts.read_text()
    assert "See docs/phases/phase-8.md" in content, (
        "docs/phase-prompts.md must contain 'See docs/phases/phase-8.md' redirect"
    )
    assert "Story 8.0" not in content, (
        "docs/phase-prompts.md must NOT contain 'Story 8.0' — full spec should be in phase-8.md"
    )
