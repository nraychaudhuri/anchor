"""Tests for documentation file existence and constraints."""

from __future__ import annotations

from pathlib import Path


def test_readme_exists_and_under_400_lines() -> None:
    readme = Path(__file__).resolve().parent.parent.parent / "README.md"
    assert readme.exists(), "README.md does not exist at repo root"
    lines = readme.read_text(encoding="utf-8").splitlines()
    assert len(lines) < 400, f"README.md has {len(lines)} lines, must be under 400"


def test_pipe_architecture_doc_exists() -> None:
    pipe_doc = Path(__file__).resolve().parent.parent.parent / "docs" / "pipe-architecture.md"
    assert pipe_doc.exists(), "docs/pipe-architecture.md does not exist"


def test_pairmode_contribution_guide_exists() -> None:
    pairmode_doc = Path(__file__).resolve().parent.parent.parent / "docs" / "pairmode" / "PAIRMODE.md"
    assert pairmode_doc.exists(), "docs/pairmode/PAIRMODE.md does not exist"


def test_changelog_exists_and_under_200_lines() -> None:
    changelog = Path(__file__).resolve().parent.parent.parent / "CHANGELOG.md"
    assert changelog.exists(), "CHANGELOG.md does not exist at repo root"
    lines = changelog.read_text(encoding="utf-8").splitlines()
    assert len(lines) < 200, f"CHANGELOG.md has {len(lines)} lines, must be under 200"


def test_contributing_exists_and_under_200_lines() -> None:
    contributing = Path(__file__).resolve().parent.parent.parent / "CONTRIBUTING.md"
    assert contributing.exists(), "CONTRIBUTING.md does not exist at repo root"
    lines = contributing.read_text(encoding="utf-8").splitlines()
    assert len(lines) < 200, f"CONTRIBUTING.md has {len(lines)} lines, must be under 200"
