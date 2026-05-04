"""Tests for skills/pairmode/scripts/spec_reader.py."""

from __future__ import annotations

import json
import pathlib

import pytest

from skills.pairmode.scripts.spec_reader import read_project_spec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_structure(
    tmp_path: pathlib.Path,
    *,
    spec_location: pathlib.Path | None = None,
    modules: dict[str, dict] | None = None,
) -> pathlib.Path:
    """Build a minimal companion + config + spec structure under tmp_path.

    Returns the companion_dir (.companion/).
    """
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir()

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    config_path = config_dir / "config.json"

    if spec_location is None:
        spec_location = tmp_path / "product-spec"

    config = {"spec_location": str(spec_location)}
    config_path.write_text(json.dumps(config))

    product = {"product": "testproduct", "config": str(config_path)}
    (companion_dir / "product.json").write_text(json.dumps(product))

    if modules is not None:
        specs_dir = spec_location / "openspec" / "specs"
        specs_dir.mkdir(parents=True)
        for module_name, spec_data in modules.items():
            module_dir = specs_dir / module_name
            module_dir.mkdir()
            (module_dir / "spec.json").write_text(json.dumps(spec_data))

    return companion_dir


# ---------------------------------------------------------------------------
# Missing product.json
# ---------------------------------------------------------------------------

class TestMissingProductJson:
    def test_returns_none_when_companion_dir_missing(self, tmp_path):
        companion_dir = tmp_path / ".companion"  # not created
        result = read_project_spec(companion_dir)
        assert result is None

    def test_returns_none_when_product_json_missing(self, tmp_path):
        companion_dir = tmp_path / ".companion"
        companion_dir.mkdir()
        # No product.json written
        result = read_project_spec(companion_dir)
        assert result is None


# ---------------------------------------------------------------------------
# Missing or empty spec files
# ---------------------------------------------------------------------------

class TestMissingSpecFiles:
    def test_returns_empty_modules_when_specs_dir_missing(self, tmp_path):
        # spec_location exists but openspec/specs/ does not
        spec_location = tmp_path / "product-spec"
        spec_location.mkdir()
        companion_dir = make_structure(
            tmp_path, spec_location=spec_location, modules=None
        )
        result = read_project_spec(companion_dir)
        assert result is not None
        assert result["modules"] == []
        assert result["spec_location"] == spec_location

    def test_returns_empty_modules_when_specs_dir_empty(self, tmp_path):
        companion_dir = make_structure(tmp_path, modules={})
        result = read_project_spec(companion_dir)
        assert result is not None
        assert result["modules"] == []


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestReadProjectSpec:
    def test_reads_single_module(self, tmp_path):
        spec = {
            "module": "auth",
            "summary": "Handles authentication.",
            "business_rules": ["Users must log in"],
            "non_negotiables": [],
            "tradeoffs": [],
            "conflicts": [],
            "lineage": [],
        }
        companion_dir = make_structure(tmp_path, modules={"auth": spec})
        result = read_project_spec(companion_dir)
        assert result is not None
        assert len(result["modules"]) == 1
        assert result["modules"][0]["module"] == "auth"

    def test_reads_multiple_modules(self, tmp_path):
        modules = {
            "auth": {"module": "auth", "summary": "Auth module"},
            "billing": {"module": "billing", "summary": "Billing module"},
            "crud": {"module": "crud", "summary": "CRUD module"},
        }
        companion_dir = make_structure(tmp_path, modules=modules)
        result = read_project_spec(companion_dir)
        assert result is not None
        assert len(result["modules"]) == 3
        names = {m["module"] for m in result["modules"]}
        assert names == {"auth", "billing", "crud"}

    def test_returns_spec_location_as_path(self, tmp_path):
        companion_dir = make_structure(tmp_path, modules={"auth": {"module": "auth"}})
        result = read_project_spec(companion_dir)
        assert isinstance(result["spec_location"], pathlib.Path)

    def test_full_spec_content_preserved(self, tmp_path):
        spec = {
            "module": "engine",
            "summary": "Core engine.",
            "business_rules": ["rule A", "rule B"],
            "non_negotiables": ["never do X"],
            "tradeoffs": [{"decision": "use postgres", "reason": "ACID", "accepted_cost": "complexity"}],
            "conflicts": [],
            "lineage": [{"session_id": "abc", "summary": "initial", "date": "2026-01-01", "resume": "claude --resume abc"}],
        }
        companion_dir = make_structure(tmp_path, modules={"engine": spec})
        result = read_project_spec(companion_dir)
        loaded = result["modules"][0]
        assert loaded["business_rules"] == ["rule A", "rule B"]
        assert loaded["non_negotiables"] == ["never do X"]
        assert loaded["tradeoffs"][0]["decision"] == "use postgres"


# ---------------------------------------------------------------------------
# Malformed JSON
# ---------------------------------------------------------------------------

class TestMalformedJson:
    def test_skips_malformed_spec_file(self, tmp_path):
        companion_dir = make_structure(
            tmp_path, modules={"auth": {"module": "auth", "summary": "ok"}}
        )
        # Corrupt one additional module by writing bad JSON directly
        spec_location = tmp_path / "product-spec"
        bad_dir = spec_location / "openspec" / "specs" / "bad-module"
        bad_dir.mkdir()
        (bad_dir / "spec.json").write_text("{ this is not json }")

        result = read_project_spec(companion_dir)
        assert result is not None
        # bad-module is skipped; auth is still present
        assert len(result["modules"]) == 1
        assert result["modules"][0]["module"] == "auth"

    def test_all_good_modules_loaded_when_one_bad(self, tmp_path):
        companion_dir = make_structure(
            tmp_path,
            modules={
                "auth": {"module": "auth"},
                "billing": {"module": "billing"},
            },
        )
        # Corrupt billing
        spec_location = tmp_path / "product-spec"
        billing_spec = spec_location / "openspec" / "specs" / "billing" / "spec.json"
        billing_spec.write_text("<<<broken>>>")

        result = read_project_spec(companion_dir)
        assert result is not None
        assert len(result["modules"]) == 1
        assert result["modules"][0]["module"] == "auth"

    def test_malformed_product_json_returns_none(self, tmp_path):
        companion_dir = tmp_path / ".companion"
        companion_dir.mkdir()
        (companion_dir / "product.json").write_text("not valid json{{{")
        result = read_project_spec(companion_dir)
        assert result is None
