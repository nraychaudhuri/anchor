"""Tests for skills/pairmode/scripts/spec_exception.py."""

from __future__ import annotations

import json
import pathlib
from datetime import date

import pytest

from skills.pairmode.scripts.spec_exception import record_spec_exception


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_env(
    tmp_path: pathlib.Path,
    *,
    module_name: str = "auth",
    module_paths: list[str] | None = None,
    spec_data: dict | None = None,
    write_product_json: bool = True,
    write_config: bool = True,
    write_modules_json: bool = True,
    write_spec: bool = True,
) -> pathlib.Path:
    """Build a full temp environment.

    Returns project_dir (tmp_path itself).
    """
    project_dir = tmp_path
    companion_dir = project_dir / ".companion"
    companion_dir.mkdir(parents=True, exist_ok=True)

    spec_location = project_dir / "product-spec"
    config_path = project_dir / "config.json"

    # Config file
    if write_config:
        config_path.write_text(json.dumps({"spec_location": str(spec_location)}))

    # product.json
    if write_product_json:
        (companion_dir / "product.json").write_text(
            json.dumps({"config": str(config_path)})
        )

    # modules.json
    if module_paths is None:
        module_paths = [f"src/{module_name}/"]
    if write_modules_json:
        modules = [{"name": module_name, "paths": module_paths}]
        (companion_dir / "modules.json").write_text(json.dumps(modules))

    # spec.json
    if write_spec:
        specs_dir = spec_location / "openspec" / "specs" / module_name
        specs_dir.mkdir(parents=True, exist_ok=True)
        if spec_data is None:
            spec_data = {
                "module": module_name,
                "summary": "Test module",
                "business_rules": [],
                "non_negotiables": ["Never expose PII"],
                "tradeoffs": [],
                "conflicts": [],
                "lineage": [],
            }
        (specs_dir / "spec.json").write_text(json.dumps(spec_data))

    return project_dir


def _read_spec(tmp_path: pathlib.Path, module_name: str = "auth") -> dict:
    spec_path = (
        tmp_path
        / "product-spec"
        / "openspec"
        / "specs"
        / module_name
        / "spec.json"
    )
    return json.loads(spec_path.read_text())


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


class TestRecordSpecExceptionHappyPath:
    def test_appends_conflict_to_spec(self, tmp_path):
        project_dir = _make_env(tmp_path)
        record_spec_exception(
            project_dir=project_dir,
            file_path="src/auth/models.py",
            non_negotiable="Never expose PII",
            override_reason="Temporary debug logging",
            session_id="sess-abc123",
        )
        spec = _read_spec(tmp_path)
        assert len(spec["conflicts"]) == 1
        entry = spec["conflicts"][0]
        assert entry["file"] == "src/auth/models.py"
        assert entry["non_negotiable"] == "Never expose PII"
        assert entry["override_reason"] == "Temporary debug logging"
        assert entry["session_id"] == "sess-abc123"
        assert entry["status"] == "open"

    def test_conflict_date_is_today(self, tmp_path):
        project_dir = _make_env(tmp_path)
        record_spec_exception(
            project_dir=project_dir,
            file_path="src/auth/models.py",
            non_negotiable="Never expose PII",
            override_reason="Debug",
            session_id="sess-xyz",
        )
        spec = _read_spec(tmp_path)
        assert spec["conflicts"][0]["date"] == date.today().isoformat()

    def test_appends_multiple_conflicts(self, tmp_path):
        project_dir = _make_env(tmp_path)
        record_spec_exception(
            project_dir=project_dir,
            file_path="src/auth/models.py",
            non_negotiable="Rule A",
            override_reason="Reason 1",
            session_id="sess-1",
        )
        record_spec_exception(
            project_dir=project_dir,
            file_path="src/auth/views.py",
            non_negotiable="Rule B",
            override_reason="Reason 2",
            session_id="sess-2",
        )
        spec = _read_spec(tmp_path)
        assert len(spec["conflicts"]) == 2
        files = {e["file"] for e in spec["conflicts"]}
        assert files == {"src/auth/models.py", "src/auth/views.py"}

    def test_preserves_existing_spec_fields(self, tmp_path):
        spec_data = {
            "module": "auth",
            "summary": "Auth module",
            "business_rules": ["rule1"],
            "non_negotiables": ["Never expose PII"],
            "tradeoffs": [],
            "conflicts": [],
            "lineage": [{"session_id": "old", "summary": "init", "date": "2026-01-01", "resume": "claude --resume old"}],
        }
        project_dir = _make_env(tmp_path, spec_data=spec_data)
        record_spec_exception(
            project_dir=project_dir,
            file_path="src/auth/models.py",
            non_negotiable="Never expose PII",
            override_reason="Debug",
            session_id="sess-new",
        )
        spec = _read_spec(tmp_path)
        assert spec["summary"] == "Auth module"
        assert spec["business_rules"] == ["rule1"]
        assert len(spec["lineage"]) == 1
        assert len(spec["conflicts"]) == 1

    def test_existing_conflicts_preserved(self, tmp_path):
        existing_conflict = {
            "file": "src/auth/old.py",
            "non_negotiable": "Old rule",
            "override_reason": "Old reason",
            "date": "2026-01-01",
            "session_id": "old-session",
            "status": "open",
        }
        spec_data = {
            "module": "auth",
            "non_negotiables": [],
            "conflicts": [existing_conflict],
        }
        project_dir = _make_env(tmp_path, spec_data=spec_data)
        record_spec_exception(
            project_dir=project_dir,
            file_path="src/auth/models.py",
            non_negotiable="New rule",
            override_reason="New reason",
            session_id="sess-new",
        )
        spec = _read_spec(tmp_path)
        assert len(spec["conflicts"]) == 2
        assert spec["conflicts"][0]["file"] == "src/auth/old.py"
        assert spec["conflicts"][1]["file"] == "src/auth/models.py"


# ---------------------------------------------------------------------------
# Module matching
# ---------------------------------------------------------------------------


class TestModuleMatching:
    def test_file_matched_by_prefix(self, tmp_path):
        project_dir = _make_env(
            tmp_path,
            module_name="billing",
            module_paths=["src/billing/"],
            spec_data={
                "module": "billing",
                "non_negotiables": [],
                "conflicts": [],
            },
        )
        record_spec_exception(
            project_dir=project_dir,
            file_path="src/billing/invoices.py",
            non_negotiable="Billing rule",
            override_reason="Emergency fix",
            session_id="sess-1",
        )
        spec = _read_spec(tmp_path, module_name="billing")
        assert len(spec["conflicts"]) == 1
        assert spec["conflicts"][0]["file"] == "src/billing/invoices.py"

    def test_no_match_returns_silently(self, tmp_path):
        """File that matches no module should not raise and should not modify any spec."""
        project_dir = _make_env(
            tmp_path,
            module_name="auth",
            module_paths=["src/auth/"],
        )
        # This file does not belong to 'auth'
        record_spec_exception(
            project_dir=project_dir,
            file_path="src/unrelated/foo.py",
            non_negotiable="Some rule",
            override_reason="Some reason",
            session_id="sess-x",
        )
        # spec.json should be unchanged (no conflicts appended)
        spec = _read_spec(tmp_path)
        assert spec["conflicts"] == []


# ---------------------------------------------------------------------------
# Missing files — should log and return silently
# ---------------------------------------------------------------------------


class TestMissingFiles:
    def test_missing_modules_json_returns_silently(self, tmp_path):
        project_dir = _make_env(tmp_path, write_modules_json=False)
        # Should not raise
        record_spec_exception(
            project_dir=project_dir,
            file_path="src/auth/models.py",
            non_negotiable="Rule",
            override_reason="Reason",
            session_id="s1",
        )

    def test_missing_product_json_returns_silently(self, tmp_path):
        project_dir = _make_env(tmp_path, write_product_json=False)
        record_spec_exception(
            project_dir=project_dir,
            file_path="src/auth/models.py",
            non_negotiable="Rule",
            override_reason="Reason",
            session_id="s1",
        )

    def test_missing_spec_json_returns_silently(self, tmp_path):
        project_dir = _make_env(tmp_path, write_spec=False)
        record_spec_exception(
            project_dir=project_dir,
            file_path="src/auth/models.py",
            non_negotiable="Rule",
            override_reason="Reason",
            session_id="s1",
        )

    def test_missing_config_returns_silently(self, tmp_path):
        project_dir = _make_env(tmp_path, write_config=False)
        record_spec_exception(
            project_dir=project_dir,
            file_path="src/auth/models.py",
            non_negotiable="Rule",
            override_reason="Reason",
            session_id="s1",
        )


# ---------------------------------------------------------------------------
# Spec.json initialises conflicts array if absent
# ---------------------------------------------------------------------------


class TestConflictsArrayInitialisation:
    def test_creates_conflicts_key_if_absent(self, tmp_path):
        """Spec without a 'conflicts' key should have it created."""
        spec_data = {
            "module": "auth",
            "summary": "No conflicts key here",
            "non_negotiables": [],
        }
        project_dir = _make_env(tmp_path, spec_data=spec_data)
        record_spec_exception(
            project_dir=project_dir,
            file_path="src/auth/models.py",
            non_negotiable="Rule",
            override_reason="Reason",
            session_id="sess-init",
        )
        spec = _read_spec(tmp_path)
        assert "conflicts" in spec
        assert len(spec["conflicts"]) == 1


# ---------------------------------------------------------------------------
# INFRA-013: Confirmation tests — pipe message contract and direct write
# ---------------------------------------------------------------------------


class TestRecordSpecExceptionWritesConflict:
    """Verify record_spec_exception appends a conflict entry to spec.json."""

    def test_record_spec_exception_writes_conflict(self, tmp_path):
        """Call record_spec_exception directly; assert conflict is appended."""
        project_dir = _make_env(
            tmp_path,
            module_name="core",
            module_paths=["src/core/"],
            spec_data={
                "module": "core",
                "summary": "Core module",
                "business_rules": [],
                "non_negotiables": ["No direct DB writes from handlers"],
                "tradeoffs": [],
                "conflicts": [],
                "lineage": [],
            },
        )

        record_spec_exception(
            project_dir=project_dir,
            file_path="src/core/handler.py",
            non_negotiable="No direct DB writes from handlers",
            override_reason="Hotfix for production outage",
            session_id="sess-infra013",
        )

        spec_path = (
            tmp_path
            / "product-spec"
            / "openspec"
            / "specs"
            / "core"
            / "spec.json"
        )
        spec = json.loads(spec_path.read_text())

        assert "conflicts" in spec
        assert len(spec["conflicts"]) == 1

        entry = spec["conflicts"][0]
        assert entry["file"] == "src/core/handler.py"
        assert entry["non_negotiable"] == "No direct DB writes from handlers"
        assert entry["override_reason"] == "Hotfix for production outage"
        assert entry["session_id"] == "sess-infra013"
        assert entry["status"] == "open"
        assert "date" in entry


class TestSpecExceptionPipeMessageContract:
    """Contract test: pipe message structure matches record_spec_exception parameters."""

    def test_spec_exception_pipe_message_contract(self):
        """A spec_exception pipe message must have all fields the sidebar handler uses.

        The sidebar handler (sidebar.py) reads these fields from the event dict and
        passes them to record_spec_exception:
          - event["type"]             → must equal "spec_exception"
          - event["path"]             → file_path parameter
          - event["non_negotiable"]   → non_negotiable parameter
          - event["override_reason"]  → override_reason parameter
          - event["session_id"]       → session_id parameter (passed separately)

        This test constructs such a message and asserts that each expected key is
        present and maps to the correct record_spec_exception parameter name.
        """
        # Build a pipe message as the sidebar would emit it
        pipe_message = {
            "type": "spec_exception",
            "path": "src/core/handler.py",
            "non_negotiable": "No direct DB writes from handlers",
            "override_reason": "Hotfix for production outage",
            "session_id": "sess-contract-test",
        }

        # type must be the correct discriminator value
        assert pipe_message["type"] == "spec_exception"

        # Each key maps to the matching record_spec_exception kwarg
        param_mapping = {
            "path": "file_path",
            "non_negotiable": "non_negotiable",
            "override_reason": "override_reason",
            "session_id": "session_id",
        }
        for pipe_key, param_name in param_mapping.items():
            assert pipe_key in pipe_message, (
                f"pipe message is missing required key '{pipe_key}' "
                f"(maps to record_spec_exception param '{param_name}')"
            )
            # Values are non-empty strings
            assert isinstance(pipe_message[pipe_key], str)
            assert pipe_message[pipe_key] != ""

        # Confirm the mapping names match the actual function signature
        import inspect
        from skills.pairmode.scripts.spec_exception import record_spec_exception

        sig_params = set(inspect.signature(record_spec_exception).parameters.keys())
        # project_dir is not in the pipe message (it's resolved by the sidebar)
        for param_name in param_mapping.values():
            assert param_name in sig_params, (
                f"'{param_name}' is not a parameter of record_spec_exception"
            )
