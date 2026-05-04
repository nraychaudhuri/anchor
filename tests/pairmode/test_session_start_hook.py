"""Tests for hooks/session_start.py — pairmode context injection."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
HOOK_PATH = REPO_ROOT / "hooks" / "session_start.py"


def _run_hook(cwd: Path) -> subprocess.CompletedProcess:
    """Invoke the SessionStart hook in ``cwd`` and return the completed process."""
    return subprocess.run(
        [sys.executable, str(HOOK_PATH)],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )


def _write_state(cwd: Path, state: dict) -> Path:
    """Write a .companion/state.json under ``cwd`` with the given state dict."""
    companion_dir = cwd / ".companion"
    companion_dir.mkdir(parents=True, exist_ok=True)
    state_path = companion_dir / "state.json"
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return state_path


def _additional_context(stdout: str) -> str:
    """Parse stdout JSON and return the additionalContext string."""
    payload = json.loads(stdout)
    return payload["hookSpecificOutput"]["additionalContext"]


def test_no_output_without_state_json(tmp_path):
    """No state.json present → hook emits nothing on stdout."""
    result = _run_hook(tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_no_output_without_pairmode_version(tmp_path):
    """state.json exists but pairmode_version absent → no output."""
    _write_state(tmp_path, {"some_other_key": "value"})
    result = _run_hook(tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_emits_pairmode_version(tmp_path):
    """state.json with pairmode_version → additionalContext mentions it."""
    _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    result = _run_hook(tmp_path)
    assert result.returncode == 0
    ctx = _additional_context(result.stdout)
    assert "Pairmode v0.1.0 is active" in ctx


def test_emits_current_story(tmp_path):
    """state.json with current_story → additionalContext mentions story id."""
    _write_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "current_story": {
                "id": "INFRA-001",
                "title": "depth guards",
                "status": "in-progress",
            },
        },
    )
    result = _run_hook(tmp_path)
    assert result.returncode == 0
    ctx = _additional_context(result.stdout)
    assert "INFRA-001" in ctx


def test_emits_no_story_message(tmp_path):
    """state.json with pairmode_version but no current_story → 'No active story'."""
    _write_state(tmp_path, {"pairmode_version": "0.1.0"})
    result = _run_hook(tmp_path)
    assert result.returncode == 0
    ctx = _additional_context(result.stdout)
    assert "No active story" in ctx


def test_sidebar_active_when_pipe_exists(tmp_path):
    """pipe_path pointing at a real file → 'Companion sidebar: active'."""
    pipe_file = tmp_path / "fake_pipe"
    pipe_file.write_text("", encoding="utf-8")
    _write_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "pipe_path": str(pipe_file),
        },
    )
    result = _run_hook(tmp_path)
    assert result.returncode == 0
    ctx = _additional_context(result.stdout)
    assert "Companion sidebar: active" in ctx


def test_sidebar_attachment_instructions_when_pipe_missing(tmp_path):
    """pipe_path pointing at non-existent path → attachment instructions emitted."""
    missing_pipe = tmp_path / "does_not_exist.pipe"
    _write_state(
        tmp_path,
        {
            "pairmode_version": "0.1.0",
            "pipe_path": str(missing_pipe),
        },
    )
    result = _run_hook(tmp_path)
    assert result.returncode == 0
    ctx = _additional_context(result.stdout)
    assert "To start" in ctx
    assert "start_sidebar.sh" in ctx
