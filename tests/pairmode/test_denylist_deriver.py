"""Tests for skills/pairmode/scripts/denylist_deriver.py."""

from __future__ import annotations

import pytest

from skills.pairmode.scripts.denylist_deriver import derive_denylist


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
    def test_empty_modules_returns_empty(self):
        assert derive_denylist([], {}) == []

    def test_module_with_no_non_negotiables_returns_empty(self):
        result = derive_denylist([make_module("auth")], {"auth": ["src/auth"]})
        assert result == []

    def test_non_negotiable_without_protection_keyword_ignored(self):
        module = make_module("auth", non_negotiables=["Keep logs for 90 days"])
        result = derive_denylist([module], {"auth": ["src/auth"]})
        assert result == []

    def test_no_paths_for_module_returns_empty(self):
        module = make_module("auth", non_negotiables=["must never allow bypass"])
        result = derive_denylist([module], {})
        assert result == []


# ---------------------------------------------------------------------------
# Protection keyword triggering
# ---------------------------------------------------------------------------


class TestProtectionKeywords:
    @pytest.mark.parametrize(
        "nn_text",
        [
            "must never expose secrets",
            "must not be modified without review",
            "This path is protected from direct writes",
            "The schema is immutable once deployed",
            "Isolation must be maintained between tenants",
            "never allow direct db access",
            "Never skip the validation layer",
        ],
    )
    def test_protection_keyword_triggers_rules(self, nn_text):
        module = make_module("core", non_negotiables=[nn_text])
        result = derive_denylist([module], {"core": ["src/core"]})
        assert len(result) > 0

    def test_no_protection_keyword_produces_no_rules(self):
        module = make_module("core", non_negotiables=["Prefer async I/O for throughput"])
        result = derive_denylist([module], {"core": ["src/core"]})
        assert result == []


# ---------------------------------------------------------------------------
# Rule field content
# ---------------------------------------------------------------------------


class TestRuleFields:
    def test_all_expected_keys_present(self):
        module = make_module("auth", non_negotiables=["must never bypass auth"])
        result = derive_denylist([module], {"auth": ["src/services/auth"]})
        assert len(result) > 0
        for rule in result:
            assert set(rule.keys()) == {"path_pattern", "non_negotiable", "module"}

    def test_non_negotiable_field_is_full_text(self):
        nn = "must never allow unauthenticated access to the admin API"
        module = make_module("auth", non_negotiables=[nn])
        result = derive_denylist([module], {"auth": ["src/services/auth"]})
        assert all(r["non_negotiable"] == nn for r in result)

    def test_module_field_matches_spec_module_name(self):
        module = make_module("billing", non_negotiables=["must not modify billing records"])
        result = derive_denylist([module], {"billing": ["src/billing"]})
        assert all(r["module"] == "billing" for r in result)

    def test_path_pattern_format_edit(self):
        module = make_module("auth", non_negotiables=["must never be bypassed"])
        result = derive_denylist([module], {"auth": ["src/services/auth"]})
        edit_rules = [r for r in result if r["path_pattern"].startswith("Edit(")]
        assert len(edit_rules) > 0
        for rule in edit_rules:
            assert rule["path_pattern"] == "Edit(src/services/auth/**)"

    def test_path_pattern_format_write(self):
        module = make_module("auth", non_negotiables=["must never be bypassed"])
        result = derive_denylist([module], {"auth": ["src/services/auth"]})
        write_rules = [r for r in result if r["path_pattern"].startswith("Write(")]
        assert len(write_rules) > 0
        for rule in write_rules:
            assert rule["path_pattern"] == "Write(src/services/auth/**)"


# ---------------------------------------------------------------------------
# Edit and Write rules are both emitted
# ---------------------------------------------------------------------------


class TestBothToolsEmitted:
    def test_both_edit_and_write_rules_emitted_per_path(self):
        module = make_module("schema", non_negotiables=["immutable schema must not change"])
        result = derive_denylist([module], {"schema": ["src/schema"]})
        patterns = {r["path_pattern"] for r in result}
        assert "Edit(src/schema/**)" in patterns
        assert "Write(src/schema/**)" in patterns

    def test_multiple_paths_produce_two_rules_each(self):
        module = make_module(
            "core",
            non_negotiables=["must not modify core internals without review"],
        )
        result = derive_denylist(
            [module], {"core": ["src/core/engine", "src/core/config"]}
        )
        patterns = {r["path_pattern"] for r in result}
        assert "Edit(src/core/engine/**)" in patterns
        assert "Write(src/core/engine/**)" in patterns
        assert "Edit(src/core/config/**)" in patterns
        assert "Write(src/core/config/**)" in patterns


# ---------------------------------------------------------------------------
# Concept keyword path matching
# ---------------------------------------------------------------------------


class TestConceptKeywordMatching:
    def test_auth_keyword_in_nn_protects_auth_paths_across_modules(self):
        """Non-negotiable mentioning 'auth' should protect paths with 'auth' in any module."""
        gateway = make_module(
            "gateway",
            non_negotiables=["must never bypass auth checks at the gateway"],
        )
        module_paths = {
            "gateway": ["src/gateway"],
            "services": ["src/services/auth", "src/services/billing"],
        }
        result = derive_denylist([gateway], module_paths)
        patterns = {r["path_pattern"] for r in result}
        # gateway's own paths
        assert "Edit(src/gateway/**)" in patterns
        # auth path from services module (contains "auth")
        assert "Edit(src/services/auth/**)" in patterns
        # billing path should NOT be included (no "auth" in path)
        assert "Edit(src/services/billing/**)" not in patterns

    def test_schema_keyword_protects_schema_paths(self):
        module = make_module(
            "core",
            non_negotiables=["The schema is immutable and must not change"],
        )
        module_paths = {
            "core": ["src/core"],
            "db": ["src/db/schema", "src/db/migrations"],
        }
        result = derive_denylist([module], module_paths)
        patterns = {r["path_pattern"] for r in result}
        assert "Edit(src/db/schema/**)" in patterns
        assert "Edit(src/db/migrations/**)" not in patterns

    def test_engine_keyword_protects_engine_paths(self):
        module = make_module(
            "policy",
            non_negotiables=["must never alter engine behavior without approval"],
        )
        module_paths = {
            "policy": ["src/policy"],
            "runtime": ["src/runtime/engine", "src/runtime/scheduler"],
        }
        result = derive_denylist([module], module_paths)
        patterns = {r["path_pattern"] for r in result}
        assert "Edit(src/runtime/engine/**)" in patterns
        assert "Edit(src/runtime/scheduler/**)" not in patterns

    def test_concept_keyword_without_protection_keyword_ignored(self):
        """A non-negotiable mentioning 'auth' but no protection keyword produces no rules."""
        module = make_module(
            "core",
            non_negotiables=["The auth module handles login"],
        )
        module_paths = {
            "core": ["src/core"],
            "services": ["src/services/auth"],
        }
        result = derive_denylist([module], module_paths)
        assert result == []


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


class TestDeduplication:
    def test_duplicate_path_and_nn_not_repeated(self):
        """Same (path_pattern, non_negotiable) pair is emitted only once."""
        nn = "must never expose auth internals"
        module = make_module("auth", non_negotiables=[nn])
        # module_paths has the same module with one path
        result = derive_denylist([module], {"auth": ["src/auth"]})
        edit_rules = [r for r in result if r["path_pattern"] == "Edit(src/auth/**)"]
        assert len(edit_rules) == 1

    def test_same_nn_different_paths_both_emitted(self):
        nn = "must not be modified"
        module = make_module("core", non_negotiables=[nn])
        result = derive_denylist([module], {"core": ["src/core/a", "src/core/b"]})
        patterns = {r["path_pattern"] for r in result}
        assert "Edit(src/core/a/**)" in patterns
        assert "Edit(src/core/b/**)" in patterns


# ---------------------------------------------------------------------------
# Business rules are ignored
# ---------------------------------------------------------------------------


class TestBusinessRulesIgnored:
    def test_business_rules_do_not_produce_deny_rules(self):
        module = make_module(
            "auth",
            business_rules=["must never allow weak passwords"],
        )
        result = derive_denylist([module], {"auth": ["src/auth"]})
        assert result == []


# ---------------------------------------------------------------------------
# Multiple modules
# ---------------------------------------------------------------------------


class TestMultipleModules:
    def test_rules_from_multiple_modules_all_included(self):
        auth = make_module("auth", non_negotiables=["must never bypass auth"])
        billing = make_module("billing", non_negotiables=["must not alter billing records"])
        module_paths = {
            "auth": ["src/auth"],
            "billing": ["src/billing"],
        }
        result = derive_denylist([auth, billing], module_paths)
        modules_seen = {r["module"] for r in result}
        assert "auth" in modules_seen
        assert "billing" in modules_seen

    def test_module_with_no_path_entry_produces_no_rules_for_that_module(self):
        auth = make_module("auth", non_negotiables=["must never bypass auth"])
        orphan = make_module("orphan", non_negotiables=["must not be touched"])
        result = derive_denylist([auth, orphan], {"auth": ["src/auth"]})
        modules_seen = {r["module"] for r in result}
        assert "auth" in modules_seen
        assert "orphan" not in modules_seen

    def test_trailing_slash_in_module_path_does_not_produce_double_slash(self):
        # modules.json entries often carry a trailing slash; patterns must not.
        m = make_module("svc", non_negotiables=["must never be bypassed"])
        result = derive_denylist([m], {"svc": ["skills/companion/"]})
        patterns = [r["path_pattern"] for r in result]
        for p in patterns:
            assert "//" not in p, f"double-slash in pattern: {p}"
        assert "Edit(skills/companion/**)" in patterns
        assert "Write(skills/companion/**)" in patterns
