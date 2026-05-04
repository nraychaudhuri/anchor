"""Tests for Story 5.4 — Permission override capture.

After the Phase 5 security audit, protected-file classification was moved
from the hook (post_tool_use.py) to the sidebar (sidebar.py) so that the
hook remains a zero-I/O thin relay.

Covers:
- Pattern matching logic (fnmatch via sidebar._check_protected)
- deny-rationale.json parsing via sidebar._load_deny_rationale
- Hook pipe message has path/tool but NO protected fields
- Sidebar _check_protected correctly classifies protected files
- display_override_prompt skip/record behaviour (unchanged)
"""

from __future__ import annotations

import fnmatch
import json
import pathlib
import re
import sys

import pytest

# ---------------------------------------------------------------------------
# Import sidebar helpers (classification now lives here)
# ---------------------------------------------------------------------------

sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from skills.companion.scripts.sidebar import (  # noqa: E402
    _RULE_RE,
    _check_protected,
    _load_deny_rationale,
    _deny_rationale_cache,
    display_override_prompt,
)


# ---------------------------------------------------------------------------
# Import hook for pipe-message shape tests
# ---------------------------------------------------------------------------

import importlib.util


def _load_hook():
    hook_path = pathlib.Path(__file__).parent.parent.parent / "hooks" / "post_tool_use.py"
    spec = importlib.util.spec_from_file_location("post_tool_use", hook_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_hook = _load_hook()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_rationale(project_dir: pathlib.Path, rules: list[dict]) -> pathlib.Path:
    """Write a minimal deny-rationale.json and return its path."""
    dr_path = project_dir / ".claude" / "settings.deny-rationale.json"
    dr_path.parent.mkdir(parents=True, exist_ok=True)
    dr_path.write_text(
        json.dumps({"rules": rules}, indent=2), encoding="utf-8"
    )
    return dr_path


def _clear_cache():
    """Clear the sidebar deny-rationale cache between tests."""
    _deny_rationale_cache.clear()


# ---------------------------------------------------------------------------
# Hook pipe-message shape — must NOT contain protected fields
# ---------------------------------------------------------------------------


def test_hook_has_no_protected_helpers():
    """The hook must no longer expose _check_protected or _load_deny_rationale."""
    assert not hasattr(_hook, "_check_protected"), (
        "Hook must not have _check_protected — classification belongs in the sidebar"
    )
    assert not hasattr(_hook, "_load_deny_rationale"), (
        "Hook must not have _load_deny_rationale — classification belongs in the sidebar"
    )


def test_hook_pipe_message_has_no_protected_field(tmp_path, monkeypatch):
    """Pipe messages from the hook must not include 'protected' or 'non_negotiable'."""
    import io

    written_data = []

    # Stub out os.open / os.write / os.close and os.path.exists so the hook
    # thinks the pipe exists and "writes" without hitting the filesystem.
    monkeypatch.setattr(_hook.os.path, "exists", lambda p: True)

    real_open = _hook.os.open

    def fake_os_open(path, flags):
        if path == _hook.PIPE_PATH:
            return 999
        return real_open(path, flags)

    monkeypatch.setattr(_hook.os, "open", fake_os_open)
    monkeypatch.setattr(_hook.os, "write", lambda fd, data: written_data.append(data))
    monkeypatch.setattr(_hook.os, "close", lambda fd: None)

    # Patch state.json read to avoid filesystem dependency
    monkeypatch.setattr(
        "builtins.open",
        lambda *a, **kw: io.StringIO('{"last_loaded_modules": ["auth"]}')
        if a and "state.json" in str(a[0])
        else open(*a, **kw),
    )

    hook_input = json.dumps({
        "tool_name": "Edit",
        "tool_input": {"file_path": "src/services/auth/middleware.ts"},
        "cwd": str(tmp_path),
        "session_id": "sess-abc",
    })
    monkeypatch.setattr("sys.stdin", __import__("io").StringIO(hook_input))

    with pytest.raises(SystemExit):
        _hook.main()

    assert written_data, "Expected at least one pipe write"
    msg = json.loads(written_data[0].decode())
    assert "path" in msg
    assert "tool" in msg
    assert "protected" not in msg, "Hook must NOT set protected field"
    assert "non_negotiable" not in msg, "Hook must NOT set non_negotiable field"
    assert "protection_rule" not in msg, "Hook must NOT set protection_rule field"


# ---------------------------------------------------------------------------
# _RULE_RE — regex extraction tests (now from sidebar)
# ---------------------------------------------------------------------------


def test_rule_re_extracts_edit_glob():
    m = _RULE_RE.match("Edit(src/services/auth/**)")
    assert m is not None
    assert m.group(1) == "src/services/auth/**"


def test_rule_re_extracts_write_glob():
    m = _RULE_RE.match("Write(docs/**)")
    assert m is not None
    assert m.group(1) == "docs/**"


def test_rule_re_extracts_bash_glob():
    m = _RULE_RE.match("Bash(scripts/*.sh)")
    assert m is not None
    assert m.group(1) == "scripts/*.sh"


def test_rule_re_no_match_plain_path():
    assert _RULE_RE.match("src/services/auth/middleware.ts") is None


# ---------------------------------------------------------------------------
# _load_deny_rationale — JSON loading (sidebar version)
# ---------------------------------------------------------------------------


def test_load_deny_rationale_returns_rules(tmp_path):
    _clear_cache()
    rules = [
        {"pattern": "Edit(src/auth/**)", "non_negotiable": "Auth must never call billing"}
    ]
    _write_rationale(tmp_path, rules)
    loaded = _load_deny_rationale(str(tmp_path))
    assert loaded == rules


def test_load_deny_rationale_missing_file_returns_empty(tmp_path):
    _clear_cache()
    result = _load_deny_rationale(str(tmp_path))
    assert result == []


def test_load_deny_rationale_malformed_json_returns_empty(tmp_path):
    _clear_cache()
    dr_path = tmp_path / ".claude" / "settings.deny-rationale.json"
    dr_path.parent.mkdir(parents=True)
    dr_path.write_text("NOT JSON", encoding="utf-8")
    result = _load_deny_rationale(str(tmp_path))
    assert result == []


def test_load_deny_rationale_no_rules_key(tmp_path):
    _clear_cache()
    dr_path = tmp_path / ".claude" / "settings.deny-rationale.json"
    dr_path.parent.mkdir(parents=True)
    dr_path.write_text(json.dumps({"other": []}), encoding="utf-8")
    result = _load_deny_rationale(str(tmp_path))
    assert result == []


# ---------------------------------------------------------------------------
# _check_protected — pattern matching (sidebar version)
# ---------------------------------------------------------------------------


def test_check_protected_match_relative(tmp_path):
    _clear_cache()
    _write_rationale(tmp_path, [
        {
            "pattern": "Edit(src/services/auth/**)",
            "non_negotiable": "Auth must never call billing directly",
        }
    ])
    protected, rule, nn = _check_protected(
        "src/services/auth/middleware.ts", str(tmp_path)
    )
    assert protected is True
    assert rule == "Edit(src/services/auth/**)"
    assert nn == "Auth must never call billing directly"


def test_check_protected_match_absolute_path(tmp_path):
    _clear_cache()
    _write_rationale(tmp_path, [
        {
            "pattern": "Edit(src/services/auth/**)",
            "non_negotiable": "Auth must never call billing directly",
        }
    ])
    abs_path = str(tmp_path / "src" / "services" / "auth" / "middleware.ts")
    protected, rule, nn = _check_protected(abs_path, str(tmp_path))
    assert protected is True


def test_check_protected_no_match(tmp_path):
    _clear_cache()
    _write_rationale(tmp_path, [
        {
            "pattern": "Edit(src/services/auth/**)",
            "non_negotiable": "Auth must never call billing",
        }
    ])
    protected, rule, nn = _check_protected(
        "src/components/Button.tsx", str(tmp_path)
    )
    assert protected is False
    assert rule == ""
    assert nn == ""


def test_check_protected_no_rationale_file(tmp_path):
    """Sidebar silently skips check when deny-rationale.json does not exist."""
    _clear_cache()
    protected, rule, nn = _check_protected(
        "src/services/auth/middleware.ts", str(tmp_path)
    )
    assert protected is False


def test_check_protected_empty_file_path(tmp_path):
    _clear_cache()
    _write_rationale(tmp_path, [
        {"pattern": "Edit(src/**)", "non_negotiable": "Do not touch src"}
    ])
    protected, rule, nn = _check_protected("", str(tmp_path))
    assert protected is False


def test_check_protected_multiple_rules_first_match_wins(tmp_path):
    _clear_cache()
    _write_rationale(tmp_path, [
        {
            "pattern": "Edit(src/services/auth/**)",
            "non_negotiable": "Auth rule",
        },
        {
            "pattern": "Edit(src/**)",
            "non_negotiable": "Broad rule",
        },
    ])
    protected, rule, nn = _check_protected(
        "src/services/auth/handler.ts", str(tmp_path)
    )
    assert protected is True
    assert nn == "Auth rule"


def test_check_protected_write_pattern_not_matched_by_edit(tmp_path):
    """Write(...) patterns should match (glob inner part is what matters)."""
    _clear_cache()
    _write_rationale(tmp_path, [
        {
            "pattern": "Write(src/services/auth/**)",
            "non_negotiable": "Write-only rule",
        }
    ])
    protected, rule, nn = _check_protected(
        "src/services/auth/middleware.ts", str(tmp_path)
    )
    # The RULE_RE strips the tool prefix; Write( pattern glob matches the path
    assert protected is True


# ---------------------------------------------------------------------------
# skip behaviour — display_override_prompt
# ---------------------------------------------------------------------------

# We test display_override_prompt in isolation using monkeypatching.


def test_display_override_prompt_skip_writes_nothing(monkeypatch, tmp_path):
    """When user presses 's', no pipe write should occur."""
    written = []

    def fake_open(path, flags):
        written.append(("open", path, flags))
        return 99  # fake fd

    def fake_write(fd, data):
        written.append(("write", fd, data))

    def fake_close(fd):
        pass

    import skills.companion.scripts.sidebar as sidebar_mod
    monkeypatch.setattr(sidebar_mod.os, "open", fake_open)
    monkeypatch.setattr(sidebar_mod.os, "write", fake_write)
    monkeypatch.setattr(sidebar_mod.os, "close", fake_close)
    monkeypatch.setattr("builtins.input", lambda: "s")

    event = {
        "file_path": "src/services/auth/middleware.ts",
        "non_negotiable": "Auth must never call billing directly",
        "protection_rule": "Edit(src/services/auth/**)",
        "session_id": "sess-123",
        "cwd": str(tmp_path),
    }
    display_override_prompt(event)

    # No pipe writes should have occurred
    pipe_writes = [w for w in written if w[0] == "write"]
    assert pipe_writes == []


def test_display_override_prompt_reason_writes_spec_exception(monkeypatch, tmp_path):
    """When user provides a reason, a spec_exception should be written to the pipe."""
    written_data = []

    def fake_open(path, flags):
        return 99

    def fake_write(fd, data):
        written_data.append(data)

    def fake_close(fd):
        pass

    import skills.companion.scripts.sidebar as sidebar_mod
    monkeypatch.setattr(sidebar_mod.os, "open", fake_open)
    monkeypatch.setattr(sidebar_mod.os, "write", fake_write)
    monkeypatch.setattr(sidebar_mod.os, "close", fake_close)
    monkeypatch.setattr("builtins.input", lambda: "emergency hotfix for production outage")

    event = {
        "file_path": "src/services/auth/middleware.ts",
        "non_negotiable": "Auth must never call billing directly",
        "protection_rule": "Edit(src/services/auth/**)",
        "session_id": "sess-123",
        "cwd": str(tmp_path),
    }
    display_override_prompt(event)

    assert len(written_data) == 1
    msg = json.loads(written_data[0].decode())
    assert msg["type"] == "spec_exception"
    assert msg["path"] == "src/services/auth/middleware.ts"
    assert msg["non_negotiable"] == "Auth must never call billing directly"
    assert msg["override_reason"] == "emergency hotfix for production outage"
    assert msg["session_id"] == "sess-123"


def test_display_override_prompt_empty_reason_skips(monkeypatch, tmp_path):
    """Empty string input is treated as skip — no pipe write."""
    written_data = []

    def fake_open(path, flags):
        return 99

    def fake_write(fd, data):
        written_data.append(data)

    def fake_close(fd):
        pass

    import skills.companion.scripts.sidebar as sidebar_mod
    monkeypatch.setattr(sidebar_mod.os, "open", fake_open)
    monkeypatch.setattr(sidebar_mod.os, "write", fake_write)
    monkeypatch.setattr(sidebar_mod.os, "close", fake_close)
    monkeypatch.setattr("builtins.input", lambda: "")

    event = {
        "file_path": "src/services/auth/middleware.ts",
        "non_negotiable": "Auth must never call billing directly",
        "protection_rule": "Edit(src/services/auth/**)",
        "session_id": "sess-123",
        "cwd": str(tmp_path),
    }
    display_override_prompt(event)

    assert written_data == []


# ---------------------------------------------------------------------------
# bootstrap.py — deny-rationale.json creation (integration sanity check)
# ---------------------------------------------------------------------------


def test_bootstrap_writes_deny_rationale(tmp_path):
    """Bootstrap should write .claude/settings.deny-rationale.json alongside settings.json."""
    from skills.pairmode.scripts.bootstrap import bootstrap
    from click.testing import CliRunner

    runner = CliRunner()
    # Create a minimal spec structure
    companion_dir = tmp_path / ".companion"
    companion_dir.mkdir()
    config_dir = tmp_path / "_config"
    config_dir.mkdir()
    spec_dir = config_dir / "openspec" / "specs" / "auth"
    spec_dir.mkdir(parents=True)
    spec_dir.joinpath("spec.json").write_text(
        json.dumps({
            "module": "auth",
            "summary": "Auth module",
            "non_negotiables": ["Auth must never call billing directly"],
            "business_rules": [],
            "tradeoffs": [],
            "lineage": [],
        }),
        encoding="utf-8",
    )
    config_path = config_dir / "config.json"
    config_path.write_text(
        json.dumps({"spec_location": str(config_dir)}), encoding="utf-8"
    )
    product_path = companion_dir / "product.json"
    product_path.write_text(
        json.dumps({"config": str(config_path)}), encoding="utf-8"
    )
    modules_path = companion_dir / "modules.json"
    modules_path.write_text(
        json.dumps([{"name": "auth", "paths": ["src/services/auth"]}]),
        encoding="utf-8",
    )

    result = runner.invoke(
        bootstrap,
        [
            "--project-dir", str(tmp_path),
            "--project-name", "TestProject",
            "--stack", "Python",
            "--build-command", "pytest",
        ],
        catch_exceptions=False,
    )
    assert result.exit_code == 0, result.output

    rationale_path = tmp_path / ".claude" / "settings.deny-rationale.json"
    assert rationale_path.exists(), "deny-rationale.json was not written"

    data = json.loads(rationale_path.read_text())
    assert "rules" in data
    # Should have at least one rule derived from the spec
    assert len(data["rules"]) > 0
    rule = data["rules"][0]
    assert "pattern" in rule
    assert "non_negotiable" in rule
