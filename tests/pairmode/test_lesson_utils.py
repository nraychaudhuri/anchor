"""Tests for lesson_utils.py."""

import json
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_data(*lessons) -> dict:
    return {"version": "1.0.0", "lessons": list(lessons)}


def _make_lesson(lid: str, trigger: str = "trigger", learning: str = "learning",
                 date: str = "2026-01-01", status: str = "active") -> dict:
    return {
        "id": lid,
        "trigger": trigger,
        "learning": learning,
        "date": date,
        "status": status,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def lessons_file(tmp_path, monkeypatch):
    """Point LESSONS_FILE at a temp file and return (module, path)."""
    import skills.pairmode.scripts.lesson_utils as lu

    tmp_file = tmp_path / "lessons.json"
    tmp_file.write_text(json.dumps({"version": "1.0.0", "lessons": []}) + "\n")

    monkeypatch.setattr(lu, "LESSONS_FILE", tmp_file)
    return lu, tmp_file


# ---------------------------------------------------------------------------
# load / save round-trip
# ---------------------------------------------------------------------------

class TestLoadSaveRoundTrip:
    def test_empty_lessons(self, lessons_file):
        lu, _ = lessons_file
        data = lu.load_lessons()
        assert data == {"version": "1.0.0", "lessons": []}

    def test_round_trip_with_lesson(self, lessons_file):
        lu, _ = lessons_file
        original = _make_data(_make_lesson("L001"))
        lu.save_lessons(original)
        loaded = lu.load_lessons()
        assert loaded == original

    def test_round_trip_preserves_version(self, lessons_file):
        lu, _ = lessons_file
        data = {"version": "2.0.0", "lessons": []}
        lu.save_lessons(data)
        loaded = lu.load_lessons()
        assert loaded["version"] == "2.0.0"


# ---------------------------------------------------------------------------
# Append-only invariant enforcement
# ---------------------------------------------------------------------------

class TestAppendOnlyInvariant:
    def test_status_change_allowed(self, lessons_file):
        lu, _ = lessons_file
        original = _make_data(_make_lesson("L001", status="active"))
        lu.save_lessons(original)

        updated = _make_data(_make_lesson("L001", status="retired"))
        lu.save_lessons(updated)  # should not raise

        loaded = lu.load_lessons()
        assert loaded["lessons"][0]["status"] == "retired"

    def test_modifying_trigger_raises(self, lessons_file):
        lu, _ = lessons_file
        lu.save_lessons(_make_data(_make_lesson("L001", trigger="original")))

        modified = _make_data(_make_lesson("L001", trigger="changed"))
        with pytest.raises(ValueError, match="trigger"):
            lu.save_lessons(modified)

    def test_modifying_learning_raises(self, lessons_file):
        lu, _ = lessons_file
        lu.save_lessons(_make_data(_make_lesson("L001", learning="original")))

        modified = _make_data(_make_lesson("L001", learning="changed"))
        with pytest.raises(ValueError, match="learning"):
            lu.save_lessons(modified)

    def test_modifying_date_raises(self, lessons_file):
        lu, _ = lessons_file
        lu.save_lessons(_make_data(_make_lesson("L001", date="2026-01-01")))

        modified = _make_data(_make_lesson("L001", date="2099-12-31"))
        with pytest.raises(ValueError, match="date"):
            lu.save_lessons(modified)

    def test_modifying_id_not_in_existing_is_new_entry(self, lessons_file):
        lu, _ = lessons_file
        lu.save_lessons(_make_data(_make_lesson("L001")))

        # Adding L002 is a new append — allowed
        updated = _make_data(_make_lesson("L001"), _make_lesson("L002"))
        lu.save_lessons(updated)  # should not raise
        loaded = lu.load_lessons()
        assert len(loaded["lessons"]) == 2

    def test_multiple_violations_first_field_reported(self, lessons_file):
        lu, _ = lessons_file
        lu.save_lessons(_make_data(_make_lesson("L001", trigger="orig", learning="orig")))

        bad = _make_data(_make_lesson("L001", trigger="changed", learning="also changed"))
        with pytest.raises(ValueError):
            lu.save_lessons(bad)

    def test_deletion_raises(self, lessons_file):
        lu, _ = lessons_file
        lu.save_lessons(_make_data(_make_lesson("L001"), _make_lesson("L002")))

        # Omitting L001 from incoming data is a deletion attempt
        with pytest.raises(ValueError, match="L001"):
            lu.save_lessons(_make_data(_make_lesson("L002")))

    def test_empty_incoming_raises_for_existing_lessons(self, lessons_file):
        lu, _ = lessons_file
        lu.save_lessons(_make_data(_make_lesson("L001")))

        with pytest.raises(ValueError, match="L001"):
            lu.save_lessons({"version": "1.0.0", "lessons": []})


# ---------------------------------------------------------------------------
# LESSONS.md generation
# ---------------------------------------------------------------------------

class TestGenerateLessonsMd:
    def test_empty_lessons(self):
        from skills.pairmode.scripts.lesson_utils import generate_lessons_md
        md = generate_lessons_md({"version": "1.0.0", "lessons": []})
        assert "# Anchor Methodology Lessons" in md
        assert "auto-generated" in md
        assert "No lessons captured yet." in md

    def test_empty_produces_placeholder(self):
        """Empty lessons list produces the standard placeholder line."""
        from skills.pairmode.scripts.lesson_utils import generate_lessons_md
        md = generate_lessons_md({"version": "1.0.0", "lessons": []})
        assert "No lessons captured yet." in md
        assert "## L" not in md  # no lesson entries

    def test_one_lesson(self):
        from skills.pairmode.scripts.lesson_utils import generate_lessons_md
        lesson = _make_lesson("L001", trigger="Builder skipped tests",
                              learning="Always run tests first.", date="2026-04-19",
                              status="active")
        md = generate_lessons_md(_make_data(lesson))
        assert "## L001 — Builder skipped tests" in md
        assert "**Date:** 2026-04-19" in md
        assert "**Status:** active" in md
        assert "**Learning:** Always run tests first." in md
        assert "No lessons captured yet." not in md

    def test_multiple_lessons(self):
        from skills.pairmode.scripts.lesson_utils import generate_lessons_md
        data = _make_data(
            _make_lesson("L001", trigger="Trigger A"),
            _make_lesson("L002", trigger="Trigger B"),
        )
        md = generate_lessons_md(data)
        assert "## L001 — Trigger A" in md
        assert "## L002 — Trigger B" in md


# ---------------------------------------------------------------------------
# next_lesson_id sequencing
# ---------------------------------------------------------------------------

class TestNextLessonId:
    def test_empty_returns_l001(self):
        from skills.pairmode.scripts.lesson_utils import next_lesson_id
        assert next_lesson_id([]) == "L001"

    def test_one_entry_returns_l002(self):
        from skills.pairmode.scripts.lesson_utils import next_lesson_id
        assert next_lesson_id([_make_lesson("L001")]) == "L002"

    def test_nine_entries_returns_l010(self):
        from skills.pairmode.scripts.lesson_utils import next_lesson_id
        lessons = [_make_lesson(f"L{i:03d}") for i in range(1, 10)]
        assert next_lesson_id(lessons) == "L010"

    def test_zero_padded_to_three_digits(self):
        from skills.pairmode.scripts.lesson_utils import next_lesson_id
        lessons = [_make_lesson(f"L{i:03d}") for i in range(1, 100)]
        assert next_lesson_id(lessons) == "L100"

    def test_gap_uses_max_not_len(self):
        """With a gap (L001, L003), returns L004 not L003."""
        from skills.pairmode.scripts.lesson_utils import next_lesson_id
        lessons = [_make_lesson("L001"), _make_lesson("L003")]
        assert next_lesson_id(lessons) == "L004"

    def test_larger_gap(self):
        """With L001, L002, L010, returns L011."""
        from skills.pairmode.scripts.lesson_utils import next_lesson_id
        lessons = [_make_lesson("L001"), _make_lesson("L002"), _make_lesson("L010")]
        assert next_lesson_id(lessons) == "L011"


# ---------------------------------------------------------------------------
# load_lessons error handling
# ---------------------------------------------------------------------------

class TestLoadLessonsErrorHandling:
    def test_missing_file_raises_runtime_error(self, tmp_path, monkeypatch):
        """load_lessons raises RuntimeError when lessons.json does not exist."""
        import skills.pairmode.scripts.lesson_utils as lu
        absent = tmp_path / "lessons.json"
        monkeypatch.setattr(lu, "LESSONS_FILE", absent)
        with pytest.raises(RuntimeError) as exc_info:
            lu.load_lessons()
        msg = str(exc_info.value)
        assert "lessons.json" in msg
        assert str(absent) in msg

    def test_existing_file_returns_list(self, lessons_file):
        """load_lessons returns a dict when file exists (existing behaviour)."""
        lu, _ = lessons_file
        result = lu.load_lessons()
        assert isinstance(result, dict)
        assert "lessons" in result
