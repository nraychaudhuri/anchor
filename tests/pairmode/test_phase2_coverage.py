"""Story 2.5 — Phase 2 test coverage pass.

Fills gaps across spec_reader, checklist_deriver, denylist_deriver, and
bootstrap integration that were not covered in Stories 2.1–2.4.
"""

from __future__ import annotations

import json
import pathlib

import pytest
from click.testing import CliRunner

from skills.pairmode.scripts.spec_reader import read_project_spec
from skills.pairmode.scripts.checklist_deriver import derive_checklist
from skills.pairmode.scripts.denylist_deriver import derive_denylist
from skills.pairmode.scripts.bootstrap import bootstrap, DEFAULT_DENY, PAIRMODE_VERSION


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_spec(
    tmp_path: pathlib.Path,
    *,
    spec_location: pathlib.Path | None = None,
    modules: dict[str, dict] | None = None,
) -> pathlib.Path:
    """Create minimal .companion + config + spec tree.  Returns companion_dir."""
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir(exist_ok=True)

    config_dir = tmp_path / "_config"
    config_dir.mkdir(exist_ok=True)
    config_path = config_dir / "config.json"

    if spec_location is None:
        spec_location = tmp_path / "_spec"

    config_path.write_text(json.dumps({"spec_location": str(spec_location)}))

    product = {"product": "testprod", "config": str(config_path)}
    (companion_dir / "product.json").write_text(json.dumps(product))

    if modules is not None:
        specs_dir = spec_location / "openspec" / "specs"
        specs_dir.mkdir(parents=True, exist_ok=True)
        for name, data in modules.items():
            mod_dir = specs_dir / name
            mod_dir.mkdir(parents=True, exist_ok=True)
            (mod_dir / "spec.json").write_text(json.dumps(data))

    return companion_dir


def _make_module(
    name: str,
    *,
    non_negotiables: list[str] | None = None,
    business_rules: list[str] | None = None,
    tradeoffs: list[dict] | None = None,
) -> dict:
    return {
        "module": name,
        "summary": f"Summary of {name}.",
        "non_negotiables": non_negotiables or [],
        "business_rules": business_rules or [],
        "tradeoffs": tradeoffs or [],
        "conflicts": [],
        "lineage": [],
    }


# ---------------------------------------------------------------------------
# spec_reader edge cases
# ---------------------------------------------------------------------------

class TestSpecReaderEdgeCases:
    def test_empty_spec_file_is_loaded_as_empty_dict(self, tmp_path):
        """A spec.json that is valid JSON but is {} should be loaded (not skipped)."""
        companion_dir = _make_spec(tmp_path, modules={"empty-mod": {}})
        result = read_project_spec(companion_dir)
        assert result is not None
        assert len(result["modules"]) == 1
        assert result["modules"][0] == {}

    def test_spec_with_no_non_negotiables_key_loaded(self, tmp_path):
        """A spec.json that omits non_negotiables should still be included."""
        spec = {"module": "core", "summary": "Core module.", "business_rules": ["rule A"]}
        companion_dir = _make_spec(tmp_path, modules={"core": spec})
        result = read_project_spec(companion_dir)
        assert result is not None
        mod = result["modules"][0]
        assert mod["module"] == "core"
        # non_negotiables key is absent — callers use .get()
        assert "non_negotiables" not in mod

    def test_spec_with_only_tradeoffs_and_no_rules_loaded(self, tmp_path):
        """A spec.json with only tradeoffs (no rules) is loaded without error."""
        spec = {
            "module": "arch",
            "tradeoffs": [
                {"decision": "chose postgres", "reason": "acid", "accepted_cost": "ops"}
            ],
        }
        companion_dir = _make_spec(tmp_path, modules={"arch": spec})
        result = read_project_spec(companion_dir)
        assert result is not None
        assert len(result["modules"]) == 1
        assert result["modules"][0]["module"] == "arch"

    def test_unicode_in_spec_fields_preserved(self, tmp_path):
        """Unicode characters in non_negotiables are round-tripped correctly."""
        spec = {
            "module": "i18n",
            "non_negotiables": ["Müssen niemals Daten verlieren — données sécurisées"],
        }
        companion_dir = _make_spec(tmp_path, modules={"i18n": spec})
        result = read_project_spec(companion_dir)
        assert result is not None
        nn = result["modules"][0]["non_negotiables"][0]
        assert "Müssen" in nn
        assert "données" in nn

    def test_product_json_missing_config_key_returns_none(self, tmp_path):
        """product.json without 'config' key should return None."""
        companion_dir = tmp_path / ".companion"
        companion_dir.mkdir()
        (companion_dir / "product.json").write_text(json.dumps({"product": "test"}))
        result = read_project_spec(companion_dir)
        assert result is None

    def test_config_missing_spec_location_returns_none(self, tmp_path):
        """config.json without 'spec_location' key should return None."""
        companion_dir = tmp_path / ".companion"
        companion_dir.mkdir()
        config_dir = tmp_path / "_config"
        config_dir.mkdir()
        config_path = config_dir / "config.json"
        config_path.write_text(json.dumps({}))  # no spec_location
        (companion_dir / "product.json").write_text(
            json.dumps({"product": "test", "config": str(config_path)})
        )
        result = read_project_spec(companion_dir)
        assert result is None

    def test_config_file_not_found_returns_none(self, tmp_path):
        """product.json pointing to a non-existent config file returns None."""
        companion_dir = tmp_path / ".companion"
        companion_dir.mkdir()
        (companion_dir / "product.json").write_text(
            json.dumps({"product": "test", "config": "/nonexistent/path/config.json"})
        )
        result = read_project_spec(companion_dir)
        assert result is None

    def test_spec_location_does_not_exist_returns_empty_modules(self, tmp_path):
        """spec_location referenced but not created on disk → empty modules list."""
        companion_dir = tmp_path / ".companion"
        companion_dir.mkdir()
        config_dir = tmp_path / "_config"
        config_dir.mkdir()
        config_path = config_dir / "config.json"
        config_path.write_text(json.dumps({"spec_location": str(tmp_path / "nowhere")}))
        (companion_dir / "product.json").write_text(
            json.dumps({"product": "test", "config": str(config_path)})
        )
        result = read_project_spec(companion_dir)
        assert result is not None
        assert result["modules"] == []


# ---------------------------------------------------------------------------
# checklist_deriver edge cases
# ---------------------------------------------------------------------------

class TestChecklistDeriverEdgeCases:
    def test_spec_with_only_tradeoffs_returns_empty(self):
        """Module with only tradeoffs (no non_negotiables or business_rules) yields nothing."""
        module = {
            "module": "arch",
            "tradeoffs": [{"decision": "postgres", "reason": "acid", "accepted_cost": "cost"}],
        }
        assert derive_checklist([module]) == []

    def test_spec_with_no_non_negotiables_key_uses_empty_default(self):
        """Module missing non_negotiables key entirely is treated as empty."""
        module = {"module": "core", "business_rules": ["rule A"]}
        result = derive_checklist([module])
        assert len(result) == 1
        assert result[0]["source"] == "business_rule"

    def test_spec_with_no_business_rules_key_uses_empty_default(self):
        """Module missing business_rules key entirely is treated as empty."""
        module = {"module": "core", "non_negotiables": ["NN rule"]}
        result = derive_checklist([module])
        assert len(result) == 1
        assert result[0]["source"] == "non_negotiable"

    def test_unicode_in_non_negotiable_preserved(self):
        """Unicode text in a non-negotiable passes through correctly."""
        rule = "Données doivent être chiffrées — Verschlüsselung ist Pflicht"
        module = _make_module("i18n", non_negotiables=[rule])
        result = derive_checklist([module])
        assert result[0]["description"] == rule
        assert result[0]["name"] == rule[:60]

    def test_unicode_rule_longer_than_60_chars_truncated_correctly(self):
        """Unicode multibyte characters are sliced by codepoint, not bytes."""
        rule = "Ü" * 80
        module = _make_module("i18n", non_negotiables=[rule])
        result = derive_checklist([module])
        assert result[0]["name"] == "Ü" * 60

    def test_whitespace_only_rule_included_as_is(self):
        """A rule that is whitespace-only is still returned (callers can filter)."""
        module = _make_module("x", non_negotiables=["   "])
        result = derive_checklist([module])
        assert len(result) == 1
        assert result[0]["description"] == "   "

    def test_multiple_modules_all_non_negotiables_before_all_business_rules(self):
        """With 3 modules each having both types, all NNs precede all BRs."""
        modules = [
            _make_module(f"m{i}", non_negotiables=[f"NN-{i}"], business_rules=[f"BR-{i}"])
            for i in range(3)
        ]
        result = derive_checklist(modules)
        sources = [item["source"] for item in result]
        last_nn = max(i for i, s in enumerate(sources) if s == "non_negotiable")
        first_br = min(i for i, s in enumerate(sources) if s == "business_rule")
        assert last_nn < first_br

    def test_single_module_with_no_name_field_uses_unknown(self):
        """Module without 'module' key gets 'unknown' as the module field."""
        module = {"non_negotiables": ["Must not break"]}
        result = derive_checklist([module])
        assert len(result) == 1
        assert result[0]["module"] == "unknown"


# ---------------------------------------------------------------------------
# denylist_deriver edge cases
# ---------------------------------------------------------------------------

class TestDenylistDeriverEdgeCases:
    def test_module_paths_with_no_matching_non_negotiables_produces_no_rules(self):
        """Paths registered for a module but non_negotiable has no keyword → no rules."""
        module = _make_module("billing", non_negotiables=["Keep audit logs for 90 days"])
        # Path registered but no protection keyword fires
        result = derive_denylist([module], {"billing": ["src/billing", "src/audit"]})
        assert result == []

    def test_conflicting_module_paths_same_path_two_modules(self):
        """Same path registered under two modules produces rules for each triggering NN."""
        auth = _make_module("auth", non_negotiables=["must never bypass auth"])
        security = _make_module("security", non_negotiables=["must not skip security checks"])
        # Both modules share the path "src/shared"
        module_paths = {
            "auth": ["src/shared"],
            "security": ["src/shared"],
        }
        result = derive_denylist([auth, security], module_paths)
        patterns = {r["path_pattern"] for r in result}
        # Both Edit and Write should appear for the shared path
        assert "Edit(src/shared/**)" in patterns
        assert "Write(src/shared/**)" in patterns
        # Rules from both modules should be present (different NNs)
        nns = {r["non_negotiable"] for r in result}
        assert any("bypass auth" in nn for nn in nns)
        assert any("skip security" in nn for nn in nns)

    def test_module_with_empty_paths_list_produces_no_rules(self):
        """Module in module_paths with paths=[] produces no rules even with triggered NN."""
        module = _make_module("core", non_negotiables=["must never be modified directly"])
        result = derive_denylist([module], {"core": []})
        assert result == []

    def test_unicode_in_non_negotiable_preserved_in_rule(self):
        """Unicode characters in non-negotiable text are preserved in the rule dict."""
        nn = "Données doivent être protégées — must never be exposed"
        module = _make_module("i18n", non_negotiables=[nn])
        result = derive_denylist([module], {"i18n": ["src/i18n"]})
        assert len(result) > 0
        assert all(r["non_negotiable"] == nn for r in result)

    def test_multiple_nns_in_same_module_all_produce_rules(self):
        """Each non-negotiable with a protection keyword generates its own rule set."""
        module = _make_module(
            "core",
            non_negotiables=[
                "must never allow direct db access",
                "must not skip the validation layer",
            ],
        )
        result = derive_denylist([module], {"core": ["src/core"]})
        nns_seen = {r["non_negotiable"] for r in result}
        assert len(nns_seen) == 2

    def test_concept_keyword_path_overlap_deduplicated(self):
        """If a module's own path also matches a concept keyword, it is not duplicated."""
        # Module named 'auth' with an 'auth' concept keyword NN, and its own path contains 'auth'
        module = _make_module("auth", non_negotiables=["must never expose auth secrets"])
        # The module's own path contains 'auth' AND the concept scan would also match it
        result = derive_denylist([module], {"auth": ["src/auth"]})
        edit_rules = [r for r in result if r["path_pattern"] == "Edit(src/auth/**)"]
        # Should appear only once regardless of double-matching
        assert len(edit_rules) == 1

    def test_modules_not_in_module_paths_produce_no_rules(self):
        """Modules whose names don't appear in module_paths dict produce no rules."""
        a = _make_module("known", non_negotiables=["must never be touched"])
        b = _make_module("unknown-mod", non_negotiables=["must not be altered"])
        result = derive_denylist([a, b], {"known": ["src/known"]})
        modules_with_rules = {r["module"] for r in result}
        assert "unknown-mod" not in modules_with_rules
        assert "known" in modules_with_rules


# ---------------------------------------------------------------------------
# Bootstrap integration test
# ---------------------------------------------------------------------------

def _build_full_companion(tmp_path: pathlib.Path) -> None:
    """Write a full .companion/ structure with product.json, modules.json,
    and two spec.json files into tmp_path.

    Module layout:
      - auth: has a protection-triggering non_negotiable + a business rule
      - payments: has a business rule only
    """
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir(exist_ok=True)

    # External spec location
    spec_location = tmp_path / "_spec"
    config_dir = tmp_path / "_config"
    config_dir.mkdir()
    config_path = config_dir / "config.json"
    config_path.write_text(json.dumps({"spec_location": str(spec_location)}))

    product = {
        "project_name": "integration-project",
        "project_description": "A fully integrated test project.",
        "config": str(config_path),
    }
    (companion_dir / "product.json").write_text(json.dumps(product, indent=2))

    # modules.json
    modules_json = [
        {"name": "auth", "paths": ["src/services/auth"]},
        {"name": "payments", "paths": ["src/services/payments"]},
    ]
    (companion_dir / "modules.json").write_text(json.dumps(modules_json, indent=2))

    # specs
    specs_dir = spec_location / "openspec" / "specs"

    auth_dir = specs_dir / "auth"
    auth_dir.mkdir(parents=True)
    auth_spec = {
        "module": "auth",
        "summary": "Handles authentication and session management.",
        "non_negotiables": [
            "Auth must never call billing directly — events only",
            "Sessions must never be stored in plaintext",
        ],
        "business_rules": [
            "Users must verify email before accessing protected resources",
        ],
        "tradeoffs": [],
        "conflicts": [],
        "lineage": [],
    }
    (auth_dir / "spec.json").write_text(json.dumps(auth_spec, indent=2))

    payments_dir = specs_dir / "payments"
    payments_dir.mkdir(parents=True)
    payments_spec = {
        "module": "payments",
        "summary": "Handles payment processing.",
        "non_negotiables": [],
        "business_rules": ["All payments must be idempotent"],
        "tradeoffs": [],
        "conflicts": [],
        "lineage": [],
    }
    (payments_dir / "spec.json").write_text(json.dumps(payments_spec, indent=2))


class TestBootstrapIntegration:
    """End-to-end integration: full .companion structure → bootstrap → assert all outputs."""

    def _run(self, tmp_path: pathlib.Path, extra_args: list[str] | None = None) -> object:
        runner = CliRunner()
        args = [
            "--project-dir", str(tmp_path),
            "--stack", "Python / FastAPI / PostgreSQL",
            "--build-command", "uv run pytest tests/ -x -q",
        ] + (extra_args or [])
        return runner.invoke(bootstrap, args, catch_exceptions=False)

    def test_exit_code_zero(self, tmp_path):
        _build_full_companion(tmp_path)
        result = self._run(tmp_path)
        assert result.exit_code == 0, result.output

    def test_all_scaffold_files_created(self, tmp_path):
        _build_full_companion(tmp_path)
        self._run(tmp_path)
        expected = [
            "CLAUDE.md",
            "CLAUDE.build.md",
            ".claude/agents/builder.md",
            ".claude/agents/reviewer.md",
            ".claude/agents/loop-breaker.md",
            ".claude/agents/security-auditor.md",
            ".claude/agents/intent-reviewer.md",
            "docs/architecture.md",
            "docs/checkpoints.md",
            "docs/phases/index.md",
            "docs/phases/phase-1.md",
        ]
        for rel in expected:
            assert (tmp_path / rel).exists(), f"Expected {rel} to exist"

    def test_project_name_from_product_json_in_claude_md(self, tmp_path):
        """project_name from product.json flows into CLAUDE.md."""
        _build_full_companion(tmp_path)
        self._run(tmp_path)
        content = (tmp_path / "CLAUDE.md").read_text()
        assert "integration-project" in content

    def test_reviewer_checklist_has_universal_items_only(self, tmp_path):
        """Reviewer checklist contains only universal items; spec text is NOT injected (L005)."""
        _build_full_companion(tmp_path)
        self._run(tmp_path)
        content = (tmp_path / ".claude/agents/reviewer.md").read_text()
        assert "Auth must never call billing directly" not in content
        assert "All payments must be idempotent" not in content
        assert "PROTECTED FILES" in content
        assert "STORY SCOPE" in content
        assert "BUILD GATE" in content

    def test_spec_derived_deny_in_settings_json(self, tmp_path):
        """Spec-derived deny patterns appear in .claude/settings.json."""
        _build_full_companion(tmp_path)
        self._run(tmp_path)
        data = json.loads((tmp_path / ".claude/settings.json").read_text())
        deny = data["permissions"]["deny"]
        assert "Edit(src/services/auth/**)" in deny
        assert "Write(src/services/auth/**)" in deny

    def test_default_deny_not_present_when_spec_derives_rules(self, tmp_path):
        """When spec yields deny rules, static DEFAULT_DENY entries are absent."""
        _build_full_companion(tmp_path)
        self._run(tmp_path)
        data = json.loads((tmp_path / ".claude/settings.json").read_text())
        deny = data["permissions"]["deny"]
        for static in DEFAULT_DENY:
            assert static not in deny, f"Static deny {static!r} should not be present"

    def test_deny_rationale_file_created(self, tmp_path):
        """settings.deny-rationale.json is created with rules linked to non-negotiables."""
        _build_full_companion(tmp_path)
        self._run(tmp_path)
        rationale_path = tmp_path / ".claude" / "settings.deny-rationale.json"
        assert rationale_path.exists()

    def test_deny_rationale_rules_linked_to_non_negotiables(self, tmp_path):
        """Each rationale rule has pattern, module, and non_negotiable fields."""
        _build_full_companion(tmp_path)
        self._run(tmp_path)
        data = json.loads((tmp_path / ".claude/settings.deny-rationale.json").read_text())
        assert data["generated_by"] == "anchor:pairmode"
        assert data["pairmode_version"] == PAIRMODE_VERSION
        assert len(data["rules"]) > 0
        for rule in data["rules"]:
            assert "pattern" in rule
            assert "module" in rule
            assert "non_negotiable" in rule
        # At least one rule should reference the auth module
        auth_rules = [r for r in data["rules"] if r["module"] == "auth"]
        assert len(auth_rules) > 0

    def test_state_json_has_pairmode_version(self, tmp_path):
        """state.json records pairmode_version after bootstrap."""
        _build_full_companion(tmp_path)
        self._run(tmp_path)
        state = json.loads((tmp_path / ".companion/state.json").read_text())
        assert state["pairmode_version"] == PAIRMODE_VERSION

    def test_build_command_in_claude_build_md(self, tmp_path):
        """Provided build command appears in CLAUDE.build.md."""
        _build_full_companion(tmp_path)
        self._run(tmp_path)
        content = (tmp_path / "CLAUDE.build.md").read_text()
        assert "uv run pytest tests/ -x -q" in content

    def test_payments_module_no_deny_rules(self, tmp_path):
        """payments module has no non_negotiables → no deny rules for payments paths."""
        _build_full_companion(tmp_path)
        self._run(tmp_path)
        data = json.loads((tmp_path / ".claude/settings.json").read_text())
        deny = data["permissions"]["deny"]
        payment_rules = [p for p in deny if "payments" in p]
        assert payment_rules == [], f"Expected no payments deny rules, got: {payment_rules}"

    def test_second_non_negotiable_also_in_deny_list(self, tmp_path):
        """Both auth non-negotiables that trigger protection keywords produce deny rules."""
        _build_full_companion(tmp_path)
        self._run(tmp_path)
        data = json.loads((tmp_path / ".claude/settings.deny-rationale.json").read_text())
        nns = {r["non_negotiable"] for r in data["rules"]}
        # Both auth NNs should appear in the rationale (they both contain "never")
        assert any("billing directly" in nn for nn in nns)
        assert any("plaintext" in nn for nn in nns)
