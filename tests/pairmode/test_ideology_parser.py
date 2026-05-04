"""Tests for skills/pairmode/scripts/ideology_parser.py."""

from __future__ import annotations

import pathlib

import pytest

from skills.pairmode.scripts import ideology_parser


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(tmp_path: pathlib.Path, filename: str, content: str) -> pathlib.Path:
    p = tmp_path / filename
    p.write_text(content, encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# parse_reconstruction_brief — convictions
# ---------------------------------------------------------------------------

class TestParseReconstructionBriefConvictions:
    def test_single_conviction_extracted(self, tmp_path):
        content = """\
# Reconstruction Brief — TestProject

## Non-negotiable ideology

### Convictions

- We prefer simplicity over complexity.

### Constraints

_(none recorded)_
"""
        p = _write(tmp_path, "reconstruction.md", content)
        result = ideology_parser.parse_reconstruction_brief(p)
        assert result["convictions"] == ["We prefer simplicity over complexity."]

    def test_multiple_convictions_extracted(self, tmp_path):
        content = """\
# Reconstruction Brief

## Non-negotiable ideology

### Convictions

- First conviction.
- Second conviction.

### Constraints

_(none)_
"""
        p = _write(tmp_path, "reconstruction.md", content)
        result = ideology_parser.parse_reconstruction_brief(p)
        assert "First conviction." in result["convictions"]
        assert "Second conviction." in result["convictions"]

    def test_no_convictions_returns_empty_list(self, tmp_path):
        content = """\
# Reconstruction Brief

## Non-negotiable ideology

### Convictions

_(no convictions recorded)_

### Constraints

_(none)_
"""
        p = _write(tmp_path, "reconstruction.md", content)
        result = ideology_parser.parse_reconstruction_brief(p)
        assert result["convictions"] == []


# ---------------------------------------------------------------------------
# parse_reconstruction_brief — constraints
# ---------------------------------------------------------------------------

class TestParseReconstructionBriefConstraints:
    def test_constraint_block_name_and_rule_extracted(self, tmp_path):
        content = """\
# Reconstruction Brief

## Non-negotiable ideology

### Convictions

_(none)_

### Constraints

#### No Direct DB Access

**Rule:** Never access the database directly from the web layer.

**Why this constraint exists:** Keeps the data layer isolated.

"""
        p = _write(tmp_path, "reconstruction.md", content)
        result = ideology_parser.parse_reconstruction_brief(p)
        assert len(result["constraints"]) == 1
        c = result["constraints"][0]
        assert c["name"] == "No Direct DB Access"
        assert "Never access the database directly" in c["rule"]

    def test_multiple_constraints_all_extracted(self, tmp_path):
        content = """\
# Reconstruction Brief

## Non-negotiable ideology

### Convictions

_(none)_

### Constraints

#### Constraint Alpha

**Rule:** Rule alpha text.

#### Constraint Beta

**Rule:** Rule beta text.

"""
        p = _write(tmp_path, "reconstruction.md", content)
        result = ideology_parser.parse_reconstruction_brief(p)
        names = [c["name"] for c in result["constraints"]]
        assert "Constraint Alpha" in names
        assert "Constraint Beta" in names

    def test_no_constraints_returns_empty_list(self, tmp_path):
        content = """\
# Reconstruction Brief

## Non-negotiable ideology

### Convictions

_(none)_

### Constraints

_(no constraints recorded)_
"""
        p = _write(tmp_path, "reconstruction.md", content)
        result = ideology_parser.parse_reconstruction_brief(p)
        assert result["constraints"] == []


# ---------------------------------------------------------------------------
# parse_reconstruction_brief — must_preserve
# ---------------------------------------------------------------------------

class TestParseReconstructionBriefMustPreserve:
    def test_must_preserve_bullets_extracted(self, tmp_path):
        content = """\
# Reconstruction Brief

## Non-negotiable ideology

### Convictions

_(none)_

## What must survive any implementation

- The event-driven architecture.
- The append-only lessons store.
"""
        p = _write(tmp_path, "reconstruction.md", content)
        result = ideology_parser.parse_reconstruction_brief(p)
        assert "The event-driven architecture." in result["must_preserve"]
        assert "The append-only lessons store." in result["must_preserve"]

    def test_must_preserve_empty_when_placeholder(self, tmp_path):
        content = """\
# Reconstruction Brief

## What must survive any implementation

_(not yet specified)_
"""
        p = _write(tmp_path, "reconstruction.md", content)
        result = ideology_parser.parse_reconstruction_brief(p)
        assert result["must_preserve"] == []


# ---------------------------------------------------------------------------
# parse_reconstruction_brief — empty file
# ---------------------------------------------------------------------------

class TestParseReconstructionBriefEmptyFile:
    def test_empty_file_returns_empty_lists_without_crash(self, tmp_path):
        p = _write(tmp_path, "reconstruction.md", "")
        result = ideology_parser.parse_reconstruction_brief(p)
        assert result["convictions"] == []
        assert result["constraints"] == []
        assert result["must_preserve"] == []
        assert result["free_to_change"] == []
        assert result["should_question"] == []
        assert result["comparison_dimensions"] == []
        assert result["value_hierarchy"] == []

    def test_file_with_only_title_returns_empty_lists(self, tmp_path):
        p = _write(tmp_path, "reconstruction.md", "# Reconstruction Brief — SomeProject\n")
        result = ideology_parser.parse_reconstruction_brief(p)
        assert result["convictions"] == []
        assert result["constraints"] == []


# ---------------------------------------------------------------------------
# parse_ideology_file — ideology.md format
# ---------------------------------------------------------------------------

MINIMAL_IDEOLOGY = """\
# Ideology — TestProject

## Core convictions

- We prefer simplicity over complexity because it reduces bugs.
- Correctness matters more than speed.

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


class TestParseIdeologyFile:
    def test_convictions_extracted_correctly(self, tmp_path):
        p = _write(tmp_path, "ideology.md", MINIMAL_IDEOLOGY)
        result = ideology_parser.parse_ideology_file(p)
        assert "We prefer simplicity over complexity because it reduces bugs." in result["convictions"]
        assert "Correctness matters more than speed." in result["convictions"]

    def test_value_hierarchy_extracted(self, tmp_path):
        p = _write(tmp_path, "ideology.md", MINIMAL_IDEOLOGY)
        result = ideology_parser.parse_ideology_file(p)
        assert len(result["value_hierarchy"]) == 1
        assert "Correctness over performance" in result["value_hierarchy"][0]

    def test_constraints_extracted_with_name_and_rule(self, tmp_path):
        p = _write(tmp_path, "ideology.md", MINIMAL_IDEOLOGY)
        result = ideology_parser.parse_ideology_file(p)
        assert len(result["constraints"]) == 1
        c = result["constraints"][0]
        assert c["name"] == "No Direct DB Access"
        assert "Never access the database directly" in c["rule"]
        assert "Keeps the data layer isolated" in c["rationale"]

    def test_must_preserve_extracted(self, tmp_path):
        p = _write(tmp_path, "ideology.md", MINIMAL_IDEOLOGY)
        result = ideology_parser.parse_ideology_file(p)
        assert "The event-driven architecture must be preserved." in result["must_preserve"]

    def test_should_question_extracted(self, tmp_path):
        p = _write(tmp_path, "ideology.md", MINIMAL_IDEOLOGY)
        result = ideology_parser.parse_ideology_file(p)
        assert "The synchronous request handler." in result["should_question"]

    def test_free_to_change_extracted(self, tmp_path):
        p = _write(tmp_path, "ideology.md", MINIMAL_IDEOLOGY)
        result = ideology_parser.parse_ideology_file(p)
        assert "The file naming conventions." in result["free_to_change"]

    def test_comparison_dimensions_extracted(self, tmp_path):
        p = _write(tmp_path, "ideology.md", MINIMAL_IDEOLOGY)
        result = ideology_parser.parse_ideology_file(p)
        assert len(result["comparison_dimensions"]) == 1
        dim = result["comparison_dimensions"][0]
        assert dim["name"] == "Constraint traceability"
        assert "Can a reader determine" in dim["description"]

    def test_project_name_extracted(self, tmp_path):
        p = _write(tmp_path, "ideology.md", MINIMAL_IDEOLOGY)
        result = ideology_parser.parse_ideology_file(p)
        assert result["project_name"] == "TestProject"

    def test_placeholder_convictions_skipped(self, tmp_path):
        content = """\
# Ideology — Proj

## Core convictions

_(not yet specified — add your convictions here)_
"""
        p = _write(tmp_path, "ideology.md", content)
        result = ideology_parser.parse_ideology_file(p)
        assert result["convictions"] == []

    def test_all_keys_present_in_result(self, tmp_path):
        p = _write(tmp_path, "ideology.md", MINIMAL_IDEOLOGY)
        result = ideology_parser.parse_ideology_file(p)
        expected_keys = {
            "project_name", "convictions", "value_hierarchy", "constraints",
            "must_preserve", "should_question", "free_to_change", "comparison_dimensions",
        }
        assert expected_keys.issubset(result.keys())


# ---------------------------------------------------------------------------
# parse_ideology_text — direct text parsing (no file I/O)
# ---------------------------------------------------------------------------

class TestParseIdeologyText:
    def test_convictions_extracted_from_text(self):
        result = ideology_parser.parse_ideology_text(MINIMAL_IDEOLOGY)
        assert "We prefer simplicity over complexity because it reduces bugs." in result["convictions"]
        assert "Correctness matters more than speed." in result["convictions"]

    def test_returns_same_output_as_parse_ideology_file(self, tmp_path):
        p = _write(tmp_path, "ideology.md", MINIMAL_IDEOLOGY)
        result_file = ideology_parser.parse_ideology_file(p)
        result_text = ideology_parser.parse_ideology_text(MINIMAL_IDEOLOGY)
        assert result_file == result_text

    def test_empty_text_returns_empty_lists(self):
        result = ideology_parser.parse_ideology_text("")
        assert result["convictions"] == []
        assert result["project_name"] == ""
        assert result["constraints"] == []
        assert result["must_preserve"] == []
        assert result["value_hierarchy"] == []

    def test_all_keys_present(self):
        result = ideology_parser.parse_ideology_text(MINIMAL_IDEOLOGY)
        expected_keys = {
            "project_name", "convictions", "value_hierarchy", "constraints",
            "must_preserve", "should_question", "free_to_change", "comparison_dimensions",
        }
        assert expected_keys.issubset(result.keys())


# ---------------------------------------------------------------------------
# Regression: reconstruct.py still works after refactor
# ---------------------------------------------------------------------------

class TestReconstructRegressionAfterRefactor:
    """Ensure reconstruct.py's parse_ideology still works (delegates to ideology_parser)."""

    def test_parse_ideology_still_callable_from_reconstruct(self, tmp_path):
        from skills.pairmode.scripts.reconstruct import parse_ideology
        result = parse_ideology(MINIMAL_IDEOLOGY)
        assert "We prefer simplicity over complexity because it reduces bugs." in result["convictions"]
        assert result["project_name"] == "TestProject"

    def test_parse_ideology_empty_text_no_crash(self, tmp_path):
        from skills.pairmode.scripts.reconstruct import parse_ideology
        result = parse_ideology("")
        assert result["convictions"] == []
        assert result["project_name"] == ""
