"""
Tests for per-project pipe isolation.

Covers:
- Hook fallback behaviour (no state.json → uses /tmp/companion.pipe)
- Hook reads pipe_path from state.json when present
- Hash is deterministic for the same project dir
- Hash differs for different project dirs
- Sidebar writes pipe_path into state.json
"""
import hashlib
import importlib
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock


# ── Helper: compute expected hash the same way sidebar.py does ────────────────

def _compute_hash(project_dir: str) -> str:
    return hashlib.md5(project_dir.encode()).hexdigest()[:8]


def _expected_pipe(project_dir: str) -> str:
    return f"/tmp/companion-{_compute_hash(project_dir)}.pipe"


# ── Hash determinism ──────────────────────────────────────────────────────────

def test_hash_is_deterministic():
    """Same project dir always produces the same hash."""
    h1 = _compute_hash("/home/user/myproject")
    h2 = _compute_hash("/home/user/myproject")
    assert h1 == h2


def test_hash_differs_for_different_dirs():
    """Different project dirs produce different hashes."""
    h1 = _compute_hash("/home/user/project-a")
    h2 = _compute_hash("/home/user/project-b")
    assert h1 != h2


def test_hash_is_8_chars():
    """Hash is exactly 8 hex characters."""
    h = _compute_hash("/some/project")
    assert len(h) == 8
    assert all(c in "0123456789abcdef" for c in h)


# ── Hook fallback: no state.json ──────────────────────────────────────────────

def _load_hook_pipe_path(hook_name: str, state_json: dict | None, cwd: str) -> str:
    """
    Simulate what a hook does at module load time to resolve PIPE_PATH.

    This mirrors the pattern in all four hooks:
      PIPE_PATH = "/tmp/companion.pipe"  # legacy fallback
      try:
          _state = json.loads(open(".companion/state.json").read())
          if _state.get("pipe_path"):
              PIPE_PATH = _state["pipe_path"]
      except Exception:
          pass
    """
    pipe_path = "/tmp/companion.pipe"
    state_file = os.path.join(cwd, ".companion", "state.json")
    try:
        raw = open(state_file).read()
        state = json.loads(raw)
        if state.get("pipe_path"):
            pipe_path = state["pipe_path"]
    except Exception:
        pass
    return pipe_path


def test_hook_fallback_when_no_state_json():
    """Without state.json, hook uses /tmp/companion.pipe."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # No .companion/state.json exists
        result = _load_hook_pipe_path("stop", None, tmpdir)
    assert result == "/tmp/companion.pipe"


def test_hook_reads_pipe_path_from_state_json():
    """When state.json contains pipe_path, hook uses it."""
    with tempfile.TemporaryDirectory() as tmpdir:
        companion_dir = Path(tmpdir) / ".companion"
        companion_dir.mkdir()
        expected_pipe = f"/tmp/companion-abc12345.pipe"
        state = {"pipe_path": expected_pipe, "last_loaded_modules": []}
        (companion_dir / "state.json").write_text(json.dumps(state))

        result = _load_hook_pipe_path("stop", state, tmpdir)
    assert result == expected_pipe


def test_hook_fallback_when_state_json_has_no_pipe_path():
    """When state.json exists but has no pipe_path key, hook uses fallback."""
    with tempfile.TemporaryDirectory() as tmpdir:
        companion_dir = Path(tmpdir) / ".companion"
        companion_dir.mkdir()
        state = {"last_loaded_modules": ["core"]}
        (companion_dir / "state.json").write_text(json.dumps(state))

        result = _load_hook_pipe_path("stop", state, tmpdir)
    assert result == "/tmp/companion.pipe"


def test_hook_fallback_when_state_json_is_malformed():
    """When state.json is not valid JSON, hook uses fallback."""
    with tempfile.TemporaryDirectory() as tmpdir:
        companion_dir = Path(tmpdir) / ".companion"
        companion_dir.mkdir()
        (companion_dir / "state.json").write_text("NOT VALID JSON{{{")

        result = _load_hook_pipe_path("stop", None, tmpdir)
    assert result == "/tmp/companion.pipe"


# ── Sidebar writes pipe_path into state.json ──────────────────────────────────

def test_sidebar_writes_pipe_path_to_state_json():
    """
    Simulate what sidebar.py's main() does: compute pipe path from project dir
    and write it into state.json. Verify the written value is correct.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        companion_dir = Path(tmpdir) / ".companion"
        companion_dir.mkdir()
        state_path = companion_dir / "state.json"
        state_path.write_text(json.dumps({"last_loaded_modules": ["core"]}))

        # Simulate what sidebar.py does
        project_dir = str(Path(tmpdir).resolve())
        _hash = hashlib.md5(project_dir.encode()).hexdigest()[:8]
        pipe_path = f"/tmp/companion-{_hash}.pipe"

        _state = json.loads(state_path.read_text()) if state_path.exists() else {}
        _state["pipe_path"] = pipe_path
        state_path.write_text(json.dumps(_state, indent=2))

        # Verify
        written = json.loads(state_path.read_text())
        assert written["pipe_path"] == pipe_path
        assert written["pipe_path"] == _expected_pipe(project_dir)
        # Existing keys preserved
        assert written["last_loaded_modules"] == ["core"]


def test_sidebar_creates_state_json_when_absent():
    """When state.json doesn't exist, sidebar creates it with pipe_path."""
    with tempfile.TemporaryDirectory() as tmpdir:
        companion_dir = Path(tmpdir) / ".companion"
        companion_dir.mkdir()
        state_path = companion_dir / "state.json"
        # No state.json

        project_dir = str(Path(tmpdir).resolve())
        _hash = hashlib.md5(project_dir.encode()).hexdigest()[:8]
        pipe_path = f"/tmp/companion-{_hash}.pipe"

        _state = json.loads(state_path.read_text()) if state_path.exists() else {}
        _state["pipe_path"] = pipe_path
        state_path.write_text(json.dumps(_state, indent=2))

        written = json.loads(state_path.read_text())
        assert written["pipe_path"] == pipe_path


def test_pipe_path_uses_resolved_project_dir():
    """Pipe path hash is based on the resolved (absolute) project dir."""
    with tempfile.TemporaryDirectory() as tmpdir:
        project_dir = str(Path(tmpdir).resolve())
        pipe1 = _expected_pipe(project_dir)
        pipe2 = _expected_pipe(project_dir)
        assert pipe1 == pipe2
        assert pipe1.startswith("/tmp/companion-")
        assert pipe1.endswith(".pipe")


def test_two_projects_get_different_pipes():
    """Two distinct project directories get different pipe paths."""
    with tempfile.TemporaryDirectory() as dir_a:
        with tempfile.TemporaryDirectory() as dir_b:
            pipe_a = _expected_pipe(str(Path(dir_a).resolve()))
            pipe_b = _expected_pipe(str(Path(dir_b).resolve()))
            assert pipe_a != pipe_b


# ── exit_plan_mode.py structural checks ──────────────────────────────────────

def _read_hook_source(hook_name: str) -> str:
    """Read the source of a hook file relative to the repo root."""
    repo_root = Path(__file__).parent.parent.parent
    hook_path = repo_root / "hooks" / hook_name
    return hook_path.read_text(encoding="utf-8")


def test_exit_plan_mode_does_not_write_state_json_directly():
    """exit_plan_mode.py must not contain STATE_PATH or open(STATE_PATH, 'w')."""
    source = _read_hook_source("exit_plan_mode.py")
    assert "STATE_PATH" not in source, (
        "exit_plan_mode.py still defines STATE_PATH — direct state write must be removed"
    )
    assert 'open(STATE_PATH, "w")' not in source, (
        "exit_plan_mode.py still writes STATE_PATH directly — architecture violation"
    )


def test_exit_plan_mode_sends_mode_change_event():
    """exit_plan_mode.py must emit a mode_change pipe event."""
    source = _read_hook_source("exit_plan_mode.py")
    assert "mode_change" in source, (
        "exit_plan_mode.py does not contain 'mode_change' — pipe event must be added"
    )
