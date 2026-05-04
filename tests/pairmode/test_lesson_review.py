"""Tests for lesson_review.py."""

from __future__ import annotations

import json
import pytest
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_lesson(
    lid: str,
    trigger: str = "some trigger",
    learning: str = "some learning",
    affects: list[str] | None = None,
    status: str = "captured",
    description: str = "some change",
) -> dict:
    if affects is None:
        affects = ["reviewer_checklist"]
    return {
        "id": lid,
        "date": "2026-01-01",
        "source_project": "test-project",
        "trigger": trigger,
        "problem": "some problem",
        "learning": learning,
        "methodology_change": {
            "affects": affects,
            "description": description,
        },
        "applies_to": ["all"],
        "status": status,
    }


def _make_data(*lessons: dict) -> dict:
    return {"version": "1.0.0", "lessons": list(lessons)}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def patched_review(tmp_path, monkeypatch):
    """Redirect LESSONS_FILE and _LESSONS_MD to tmp_path; return (module, lessons_json, lessons_md)."""
    import skills.pairmode.scripts.lesson_utils as lu
    import skills.pairmode.scripts.lesson_review as lr

    lessons_json = tmp_path / "lessons.json"
    lessons_md = tmp_path / "LESSONS.md"

    lessons_json.write_text(
        json.dumps({"version": "1.0.0", "lessons": []}) + "\n"
    )

    monkeypatch.setattr(lu, "LESSONS_FILE", lessons_json)
    monkeypatch.setattr(lr, "_LESSONS_MD", lessons_md)

    return lr, lessons_json, lessons_md


@pytest.fixture()
def patched_review_with_templates(tmp_path, monkeypatch):
    """Like patched_review but also creates fake template files and patches _ANCHOR_ROOT."""
    import skills.pairmode.scripts.lesson_utils as lu
    import skills.pairmode.scripts.lesson_review as lr

    lessons_json = tmp_path / "lessons.json"
    lessons_md = tmp_path / "LESSONS.md"

    lessons_json.write_text(
        json.dumps({"version": "1.0.0", "lessons": []}) + "\n"
    )

    # Create the template directory structure expected by apply_template_change
    templates_root = tmp_path
    (templates_root / "skills" / "pairmode" / "templates").mkdir(parents=True)
    (templates_root / "skills" / "pairmode" / "templates" / "agents").mkdir(parents=True)

    (templates_root / "skills" / "pairmode" / "templates" / "CLAUDE.md.j2").write_text(
        "# CLAUDE.md template\n", encoding="utf-8"
    )
    (templates_root / "skills" / "pairmode" / "templates" / "CLAUDE.build.md.j2").write_text(
        "# CLAUDE.build.md template\n", encoding="utf-8"
    )
    (templates_root / "skills" / "pairmode" / "templates" / "agents" / "builder.md.j2").write_text(
        "# builder.md template\n", encoding="utf-8"
    )

    monkeypatch.setattr(lu, "LESSONS_FILE", lessons_json)
    monkeypatch.setattr(lr, "_LESSONS_MD", lessons_md)
    monkeypatch.setattr(lr, "_ANCHOR_ROOT", templates_root)

    return lr, lessons_json, lessons_md, templates_root


# ---------------------------------------------------------------------------
# load_reviewable_lessons
# ---------------------------------------------------------------------------

class TestLoadReviewableLessons:
    def test_returns_captured_lessons(self, patched_review, monkeypatch):
        import skills.pairmode.scripts.lesson_utils as lu
        lr, lessons_json, _ = patched_review
        data = _make_data(_make_lesson("L001", status="captured"))
        lessons_json.write_text(json.dumps(data) + "\n")

        result = lr.load_reviewable_lessons()
        assert len(result) == 1
        assert result[0]["id"] == "L001"

    def test_returns_reviewed_lessons(self, patched_review):
        lr, lessons_json, _ = patched_review
        data = _make_data(_make_lesson("L001", status="reviewed"))
        lessons_json.write_text(json.dumps(data) + "\n")

        result = lr.load_reviewable_lessons()
        assert len(result) == 1
        assert result[0]["id"] == "L001"

    def test_excludes_applied_lessons(self, patched_review):
        lr, lessons_json, _ = patched_review
        data = _make_data(_make_lesson("L001", status="applied"))
        lessons_json.write_text(json.dumps(data) + "\n")

        result = lr.load_reviewable_lessons()
        assert result == []

    def test_excludes_other_statuses(self, patched_review):
        lr, lessons_json, _ = patched_review
        data = _make_data(
            _make_lesson("L001", status="active"),
            _make_lesson("L002", status="retired"),
            _make_lesson("L003", status="incorporated"),
        )
        lessons_json.write_text(json.dumps(data) + "\n")

        result = lr.load_reviewable_lessons()
        assert result == []

    def test_mixed_statuses_only_correct_returned(self, patched_review):
        lr, lessons_json, _ = patched_review
        data = _make_data(
            _make_lesson("L001", status="captured"),
            _make_lesson("L002", status="applied"),
            _make_lesson("L003", status="reviewed"),
            _make_lesson("L004", status="active"),
        )
        lessons_json.write_text(json.dumps(data) + "\n")

        result = lr.load_reviewable_lessons()
        ids = [l["id"] for l in result]
        assert set(ids) == {"L001", "L003"}

    def test_empty_lessons(self, patched_review):
        lr, _, _ = patched_review
        result = lr.load_reviewable_lessons()
        assert result == []


# ---------------------------------------------------------------------------
# group_lessons_by_affects
# ---------------------------------------------------------------------------

class TestGroupLessonsByAffects:
    def test_single_lesson_single_affects(self, patched_review):
        lr, _, _ = patched_review
        lessons = [_make_lesson("L001", affects=["reviewer_checklist"])]
        groups = lr.group_lessons_by_affects(lessons)
        assert "reviewer_checklist" in groups
        assert groups["reviewer_checklist"][0]["id"] == "L001"

    def test_lesson_with_all_appears_in_all_groups(self, patched_review):
        lr, _, _ = patched_review
        lessons = [_make_lesson("L001", affects=["all"])]
        groups = lr.group_lessons_by_affects(lessons)

        # Should appear in every known affects key
        for key in ("reviewer_checklist", "builder_agent", "orchestrator", "checkpoint_sequence"):
            assert key in groups, f"Expected '{key}' in groups"
            assert any(l["id"] == "L001" for l in groups[key])

    def test_multiple_affects(self, patched_review):
        lr, _, _ = patched_review
        lessons = [_make_lesson("L001", affects=["reviewer_checklist", "builder_agent"])]
        groups = lr.group_lessons_by_affects(lessons)
        assert "reviewer_checklist" in groups
        assert "builder_agent" in groups
        assert groups["reviewer_checklist"][0]["id"] == "L001"
        assert groups["builder_agent"][0]["id"] == "L001"

    def test_multiple_lessons_in_same_group(self, patched_review):
        lr, _, _ = patched_review
        lessons = [
            _make_lesson("L001", affects=["reviewer_checklist"]),
            _make_lesson("L002", affects=["reviewer_checklist"]),
        ]
        groups = lr.group_lessons_by_affects(lessons)
        assert len(groups["reviewer_checklist"]) == 2

    def test_empty_list_returns_empty_dict(self, patched_review):
        lr, _, _ = patched_review
        groups = lr.group_lessons_by_affects([])
        assert groups == {}

    def test_all_affects_does_not_duplicate_within_group(self, patched_review):
        """A lesson with affects=["all"] should appear exactly once per group."""
        lr, _, _ = patched_review
        lessons = [_make_lesson("L001", affects=["all"])]
        groups = lr.group_lessons_by_affects(lessons)
        for key, group_lessons in groups.items():
            count = sum(1 for l in group_lessons if l["id"] == "L001")
            assert count == 1, f"L001 appeared {count} times in group '{key}'"


# ---------------------------------------------------------------------------
# propose_template_change
# ---------------------------------------------------------------------------

class TestProposeTemplateChange:
    def test_reviewer_checklist_maps_to_claude_md(self, patched_review):
        lr, _, _ = patched_review
        lesson = _make_lesson("L001", affects=["reviewer_checklist"])
        proposals = lr.propose_template_change(lesson)
        assert len(proposals) == 1
        assert proposals[0]["template_file"] == "skills/pairmode/templates/CLAUDE.md.j2"

    def test_builder_agent_maps_to_builder_md(self, patched_review):
        lr, _, _ = patched_review
        lesson = _make_lesson("L001", affects=["builder_agent"])
        proposals = lr.propose_template_change(lesson)
        assert len(proposals) == 1
        assert proposals[0]["template_file"] == "skills/pairmode/templates/agents/builder.md.j2"

    def test_orchestrator_maps_to_claude_build_md(self, patched_review):
        lr, _, _ = patched_review
        lesson = _make_lesson("L001", affects=["orchestrator"])
        proposals = lr.propose_template_change(lesson)
        assert len(proposals) == 1
        assert proposals[0]["template_file"] == "skills/pairmode/templates/CLAUDE.build.md.j2"

    def test_checkpoint_sequence_maps_to_claude_build_md(self, patched_review):
        lr, _, _ = patched_review
        lesson = _make_lesson("L001", affects=["checkpoint_sequence"])
        proposals = lr.propose_template_change(lesson)
        assert len(proposals) == 1
        assert proposals[0]["template_file"] == "skills/pairmode/templates/CLAUDE.build.md.j2"

    def test_all_affects_returns_multiple_proposals(self, patched_review):
        lr, _, _ = patched_review
        lesson = _make_lesson("L001", affects=["all"])
        proposals = lr.propose_template_change(lesson)
        assert len(proposals) > 1

    def test_all_affects_covers_all_template_files(self, patched_review):
        lr, _, _ = patched_review
        lesson = _make_lesson("L001", affects=["all"])
        proposals = lr.propose_template_change(lesson)
        template_files = {p["template_file"] for p in proposals}
        expected = {
            "skills/pairmode/templates/CLAUDE.md.j2",
            "skills/pairmode/templates/agents/builder.md.j2",
            "skills/pairmode/templates/CLAUDE.build.md.j2",
        }
        assert template_files == expected

    def test_proposal_contains_lesson_context(self, patched_review):
        lr, _, _ = patched_review
        lesson = _make_lesson("L001", trigger="My trigger", learning="My learning",
                               affects=["reviewer_checklist"], description="My description")
        proposals = lr.propose_template_change(lesson)
        proposal = proposals[0]
        assert proposal["lesson_id"] == "L001"
        assert proposal["lesson_trigger"] == "My trigger"
        assert proposal["lesson_learning"] == "My learning"
        assert proposal["description"] == "My description"
        assert proposal["affects"] == "reviewer_checklist"

    def test_multiple_affects_returns_one_proposal_per_affects(self, patched_review):
        lr, _, _ = patched_review
        lesson = _make_lesson("L001", affects=["reviewer_checklist", "builder_agent"])
        proposals = lr.propose_template_change(lesson)
        assert len(proposals) == 2
        affects_values = {p["affects"] for p in proposals}
        assert affects_values == {"reviewer_checklist", "builder_agent"}


# ---------------------------------------------------------------------------
# apply_template_change
# ---------------------------------------------------------------------------

class TestApplyTemplateChange:
    def test_appends_comment_block(self, patched_review_with_templates):
        lr, lessons_json, _, templates_root = patched_review_with_templates
        lesson = _make_lesson("L001", affects=["reviewer_checklist"])
        proposals = lr.propose_template_change(lesson)
        proposal = proposals[0]

        lr.apply_template_change(proposal, "Do something new", templates_root=templates_root)

        template_path = templates_root / proposal["template_file"]
        content = template_path.read_text(encoding="utf-8")
        assert "{# LESSON L001: Do something new #}" in content

    def test_comment_format(self, patched_review_with_templates):
        lr, _, _, templates_root = patched_review_with_templates
        lesson = _make_lesson("L002", affects=["builder_agent"])
        proposals = lr.propose_template_change(lesson)
        proposal = proposals[0]

        lr.apply_template_change(proposal, "Some change text", templates_root=templates_root)

        template_path = templates_root / proposal["template_file"]
        content = template_path.read_text(encoding="utf-8")
        assert "{# LESSON L002: Some change text #}" in content

    def test_existing_content_preserved(self, patched_review_with_templates):
        lr, _, _, templates_root = patched_review_with_templates
        lesson = _make_lesson("L001", affects=["reviewer_checklist"])
        proposals = lr.propose_template_change(lesson)
        proposal = proposals[0]

        lr.apply_template_change(proposal, "New change", templates_root=templates_root)

        template_path = templates_root / proposal["template_file"]
        content = template_path.read_text(encoding="utf-8")
        # Original content still present
        assert "# CLAUDE.md template" in content
        # New comment appended
        assert "{# LESSON L001: New change #}" in content

    def test_multiple_applications_accumulate(self, patched_review_with_templates):
        lr, _, _, templates_root = patched_review_with_templates
        lesson1 = _make_lesson("L001", affects=["reviewer_checklist"])
        lesson2 = _make_lesson("L002", affects=["reviewer_checklist"])

        proposals1 = lr.propose_template_change(lesson1)
        proposals2 = lr.propose_template_change(lesson2)

        lr.apply_template_change(proposals1[0], "First change", templates_root=templates_root)
        lr.apply_template_change(proposals2[0], "Second change", templates_root=templates_root)

        template_path = templates_root / proposals1[0]["template_file"]
        content = template_path.read_text(encoding="utf-8")
        assert "{# LESSON L001: First change #}" in content
        assert "{# LESSON L002: Second change #}" in content

    def test_path_traversal_raises(self, patched_review_with_templates):
        lr, _, _, templates_root = patched_review_with_templates
        traversal_proposal = {
            "lesson_id": "L001",
            "affects": "reviewer_checklist",
            "template_file": "../../etc/passwd",
            "description": "malicious",
            "lesson_trigger": "t",
            "lesson_learning": "l",
        }
        with pytest.raises(ValueError, match="outside templates directory"):
            lr.apply_template_change(traversal_proposal, "evil", templates_root=templates_root)


# ---------------------------------------------------------------------------
# mark_lesson_status
# ---------------------------------------------------------------------------

class TestMarkLessonStatus:
    def test_marks_status_applied(self, patched_review):
        lr, lessons_json, _ = patched_review
        data = _make_data(_make_lesson("L001", status="captured"))
        lessons_json.write_text(json.dumps(data) + "\n")

        lr.mark_lesson_status("L001", "applied")

        loaded = json.loads(lessons_json.read_text())
        assert loaded["lessons"][0]["status"] == "applied"

    def test_marks_status_reviewed(self, patched_review):
        lr, lessons_json, _ = patched_review
        data = _make_data(_make_lesson("L001", status="captured"))
        lessons_json.write_text(json.dumps(data) + "\n")

        lr.mark_lesson_status("L001", "reviewed")

        loaded = json.loads(lessons_json.read_text())
        assert loaded["lessons"][0]["status"] == "reviewed"

    def test_only_status_changes_no_other_mutation(self, patched_review):
        lr, lessons_json, _ = patched_review
        lesson = _make_lesson("L001", trigger="Original trigger", status="captured")
        data = _make_data(lesson)
        lessons_json.write_text(json.dumps(data) + "\n")

        lr.mark_lesson_status("L001", "applied")

        loaded = json.loads(lessons_json.read_text())
        # trigger should be unchanged
        assert loaded["lessons"][0]["trigger"] == "Original trigger"

    def test_other_lessons_unaffected(self, patched_review):
        lr, lessons_json, _ = patched_review
        data = _make_data(
            _make_lesson("L001", status="captured"),
            _make_lesson("L002", status="captured"),
        )
        lessons_json.write_text(json.dumps(data) + "\n")

        lr.mark_lesson_status("L001", "applied")

        loaded = json.loads(lessons_json.read_text())
        assert loaded["lessons"][1]["status"] == "captured"

    def test_append_only_invariant_enforced(self, patched_review):
        """mark_lesson_status goes through save_lessons which enforces append-only."""
        import skills.pairmode.scripts.lesson_utils as lu
        lr, lessons_json, _ = patched_review
        data = _make_data(_make_lesson("L001", trigger="original", status="captured"))
        lessons_json.write_text(json.dumps(data) + "\n")

        # Manually corrupt the data to test invariant — save_lessons should catch it
        corrupted = json.loads(lessons_json.read_text())
        corrupted["lessons"][0]["trigger"] = "changed"
        corrupted["lessons"][0]["status"] = "applied"

        with pytest.raises(ValueError, match="trigger"):
            lu.save_lessons(corrupted)


# ---------------------------------------------------------------------------
# regenerate_lessons_md
# ---------------------------------------------------------------------------

class TestRegenerateLessonsMd:
    def test_writes_lessons_md(self, patched_review):
        lr, lessons_json, lessons_md = patched_review
        data = _make_data(_make_lesson("L001", trigger="My trigger", status="captured"))
        lessons_json.write_text(json.dumps(data) + "\n")

        lr.regenerate_lessons_md()

        assert lessons_md.exists()
        content = lessons_md.read_text(encoding="utf-8")
        assert "# Anchor Methodology Lessons" in content
        assert "My trigger" in content

    def test_updates_when_status_changes(self, patched_review):
        lr, lessons_json, lessons_md = patched_review
        data = _make_data(_make_lesson("L001", status="captured"))
        lessons_json.write_text(json.dumps(data) + "\n")

        lr.regenerate_lessons_md()
        first_content = lessons_md.read_text(encoding="utf-8")
        assert "captured" in first_content

        # Update status and regenerate
        data["lessons"][0]["status"] = "applied"
        lessons_json.write_text(json.dumps(data) + "\n")
        lr.regenerate_lessons_md()

        second_content = lessons_md.read_text(encoding="utf-8")
        assert "applied" in second_content

    def test_empty_lessons_writes_no_lessons_message(self, patched_review):
        lr, _, lessons_md = patched_review
        lr.regenerate_lessons_md()

        content = lessons_md.read_text(encoding="utf-8")
        assert "No lessons captured yet." in content


# ---------------------------------------------------------------------------
# all affects: propose_template_change returns multiple proposals
# ---------------------------------------------------------------------------

class TestAllAffectsMultipleProposals:
    def test_all_returns_one_proposal_per_template_file(self, patched_review):
        lr, _, _ = patched_review
        lesson = _make_lesson("L001", affects=["all"])
        proposals = lr.propose_template_change(lesson)

        # Should return multiple proposals
        assert len(proposals) > 1

        # Each proposal is for a different template file
        template_files = [p["template_file"] for p in proposals]
        assert len(template_files) == len(set(template_files)), "Duplicate template files found"

    def test_all_proposals_share_same_lesson_id(self, patched_review):
        lr, _, _ = patched_review
        lesson = _make_lesson("L001", affects=["all"])
        proposals = lr.propose_template_change(lesson)

        for proposal in proposals:
            assert proposal["lesson_id"] == "L001"

    def test_all_proposals_have_affects_set_to_all(self, patched_review):
        lr, _, _ = patched_review
        lesson = _make_lesson("L001", affects=["all"])
        proposals = lr.propose_template_change(lesson)

        for proposal in proposals:
            assert proposal["affects"] == "all"


# ---------------------------------------------------------------------------
# CLI output clarity tests
# ---------------------------------------------------------------------------

class TestCLIOutputClarity:
    def test_approved_lesson_output_contains_action_required(self, patched_review_with_templates):
        """Approving a lesson must print ACTION REQUIRED in the CLI output."""
        from click.testing import CliRunner
        import skills.pairmode.scripts.lesson_utils as lu

        lr, lessons_json, _, templates_root = patched_review_with_templates

        data = _make_data(_make_lesson("L001", status="captured", description="Add test gate"))
        lessons_json.write_text(__import__("json").dumps(data) + "\n")

        # Patch _ANCHOR_ROOT so apply_template_change uses the tmp templates
        import skills.pairmode.scripts.lesson_review as lr_mod
        original_root = lr_mod._ANCHOR_ROOT
        lr_mod._ANCHOR_ROOT = templates_root
        try:
            runner = CliRunner()
            result = runner.invoke(lr_mod.cli, ["--approve", "L001"])
        finally:
            lr_mod._ANCHOR_ROOT = original_root

        assert result.exit_code == 0, result.output
        assert "ACTION REQUIRED" in result.output

    def test_end_of_run_summary_contains_review_complete(self, patched_review_with_templates):
        """End-of-run summary must contain REVIEW COMPLETE."""
        from click.testing import CliRunner
        import skills.pairmode.scripts.lesson_utils as lu

        lr, lessons_json, _, templates_root = patched_review_with_templates

        data = _make_data(
            _make_lesson("L001", status="captured", description="Add test gate"),
            _make_lesson("L002", status="captured", description="Another change"),
        )
        lessons_json.write_text(__import__("json").dumps(data) + "\n")

        import skills.pairmode.scripts.lesson_review as lr_mod
        original_root = lr_mod._ANCHOR_ROOT
        lr_mod._ANCHOR_ROOT = templates_root
        try:
            runner = CliRunner()
            result = runner.invoke(lr_mod.cli, ["--approve", "L001", "--reject", "L002"])
        finally:
            lr_mod._ANCHOR_ROOT = original_root

        assert result.exit_code == 0, result.output
        assert "REVIEW COMPLETE" in result.output
        assert "1 lesson(s) annotated" in result.output
        assert "1 lesson(s) deferred" in result.output
