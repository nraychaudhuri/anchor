"""Tests for skills/pairmode/scripts/checklist_deriver.py."""

from __future__ import annotations

from skills.pairmode.scripts.checklist_deriver import derive_checklist


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_module(
    name: str,
    *,
    non_negotiables: list[str] | None = None,
    business_rules: list[str] | None = None,
) -> dict:
    return {
        "module": name,
        "summary": f"Summary of {name}.",
        "non_negotiables": non_negotiables or [],
        "business_rules": business_rules or [],
        "tradeoffs": [],
        "conflicts": [],
        "lineage": [],
    }


# ---------------------------------------------------------------------------
# Empty / minimal inputs
# ---------------------------------------------------------------------------

class TestEmptyInputs:
    def test_empty_list_returns_empty(self):
        assert derive_checklist([]) == []

    def test_module_with_no_rules_returns_empty(self):
        result = derive_checklist([make_module("auth")])
        assert result == []

    def test_module_with_empty_lists_returns_empty(self):
        module = make_module("auth", non_negotiables=[], business_rules=[])
        assert derive_checklist([module]) == []


# ---------------------------------------------------------------------------
# Severity mapping
# ---------------------------------------------------------------------------

class TestSeverityMapping:
    def test_non_negotiable_becomes_critical(self):
        module = make_module("auth", non_negotiables=["Never store plaintext passwords"])
        result = derive_checklist([module])
        assert len(result) == 1
        assert result[0]["severity"] == "CRITICAL"
        assert result[0]["source"] == "non_negotiable"

    def test_business_rule_becomes_high(self):
        module = make_module("auth", business_rules=["Users must verify email before login"])
        result = derive_checklist([module])
        assert len(result) == 1
        assert result[0]["severity"] == "HIGH"
        assert result[0]["source"] == "business_rule"

    def test_mixed_module_preserves_correct_severities(self):
        module = make_module(
            "auth",
            non_negotiables=["No plaintext passwords"],
            business_rules=["Rate-limit login attempts"],
        )
        result = derive_checklist([module])
        criticals = [i for i in result if i["severity"] == "CRITICAL"]
        highs = [i for i in result if i["severity"] == "HIGH"]
        assert len(criticals) == 1
        assert len(highs) == 1


# ---------------------------------------------------------------------------
# Item field content
# ---------------------------------------------------------------------------

class TestItemFields:
    def test_description_is_full_rule_text(self):
        rule = "All writes must be idempotent to handle retries safely"
        module = make_module("engine", non_negotiables=[rule])
        result = derive_checklist([module])
        assert result[0]["description"] == rule

    def test_name_is_truncated_to_60_chars(self):
        rule = "A" * 80
        module = make_module("engine", non_negotiables=[rule])
        result = derive_checklist([module])
        assert result[0]["name"] == "A" * 60

    def test_name_short_rule_not_truncated(self):
        rule = "Short rule"
        module = make_module("engine", non_negotiables=[rule])
        result = derive_checklist([module])
        assert result[0]["name"] == rule

    def test_module_field_matches_spec_module_name(self):
        module = make_module("billing", non_negotiables=["No free rides"])
        result = derive_checklist([module])
        assert result[0]["module"] == "billing"

    def test_all_expected_keys_present(self):
        module = make_module("x", non_negotiables=["rule"])
        item = derive_checklist([module])[0]
        assert set(item.keys()) == {"name", "description", "severity", "source", "module"}


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_same_non_negotiable_in_two_modules_merged(self):
        rule = "Never expose internal stack traces"
        a = make_module("auth", non_negotiables=[rule])
        b = make_module("api", non_negotiables=[rule])
        result = derive_checklist([a, b])
        assert len(result) == 1
        assert "auth" in result[0]["module"]
        assert "api" in result[0]["module"]

    def test_same_business_rule_in_two_modules_merged(self):
        rule = "All timestamps must be UTC"
        a = make_module("core", business_rules=[rule])
        b = make_module("reporting", business_rules=[rule])
        result = derive_checklist([a, b])
        assert len(result) == 1
        assert "core" in result[0]["module"]
        assert "reporting" in result[0]["module"]

    def test_merged_module_names_comma_separated(self):
        rule = "Use TLS everywhere"
        modules = [make_module(name, non_negotiables=[rule]) for name in ["a", "b", "c"]]
        result = derive_checklist(modules)
        assert len(result) == 1
        parts = [p.strip() for p in result[0]["module"].split(",")]
        assert set(parts) == {"a", "b", "c"}

    def test_same_rule_text_different_source_not_merged(self):
        rule = "Validate all inputs"
        a = make_module("x", non_negotiables=[rule])
        b = make_module("y", business_rules=[rule])
        result = derive_checklist([a, b])
        assert len(result) == 2

    def test_different_rule_texts_not_merged(self):
        a = make_module("x", non_negotiables=["Rule A"])
        b = make_module("y", non_negotiables=["Rule B"])
        result = derive_checklist([a, b])
        assert len(result) == 2

    def test_duplicate_module_not_listed_twice_in_module_field(self):
        """Same module providing the same rule twice (unlikely but guarded)."""
        rule = "Idempotent writes"
        module = {
            "module": "engine",
            "non_negotiables": [rule, rule],
            "business_rules": [],
        }
        result = derive_checklist([module])
        assert len(result) == 1
        assert result[0]["module"] == "engine"


# ---------------------------------------------------------------------------
# Ordering
# ---------------------------------------------------------------------------

class TestOrdering:
    def test_non_negotiables_appear_before_business_rules(self):
        module = make_module(
            "x",
            non_negotiables=["NN rule"],
            business_rules=["BR rule"],
        )
        result = derive_checklist([module])
        sources = [i["source"] for i in result]
        assert sources.index("non_negotiable") < sources.index("business_rule")

    def test_order_preserved_across_multiple_modules(self):
        a = make_module("a", non_negotiables=["NN-A"], business_rules=["BR-A"])
        b = make_module("b", non_negotiables=["NN-B"], business_rules=["BR-B"])
        result = derive_checklist([a, b])
        # Both NNs come before both BRs
        nn_indices = [i for i, item in enumerate(result) if item["source"] == "non_negotiable"]
        br_indices = [i for i, item in enumerate(result) if item["source"] == "business_rule"]
        assert max(nn_indices) < min(br_indices)


# ---------------------------------------------------------------------------
# Universal items NOT included
# ---------------------------------------------------------------------------

class TestUniversalItemsNotIncluded:
    """Universal items are appended by templates, not by derive_checklist."""

    def test_no_protected_files_item_returned(self):
        module = make_module("x", non_negotiables=["some rule"])
        result = derive_checklist([module])
        descriptions = [i["description"] for i in result]
        assert not any("PROTECTED FILES" in d for d in descriptions)

    def test_no_story_scope_item_returned(self):
        module = make_module("x", business_rules=["some rule"])
        result = derive_checklist([module])
        descriptions = [i["description"] for i in result]
        assert not any("STORY SCOPE" in d for d in descriptions)

    def test_source_is_never_universal(self):
        module = make_module("x", non_negotiables=["r1"], business_rules=["r2"])
        result = derive_checklist([module])
        sources = {i["source"] for i in result}
        assert "universal" not in sources
