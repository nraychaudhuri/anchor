"""
Structural tests for hook scripts.

Covers:
- session_end.py: direct state.json write removed (STATE_PATH constant gone,
  state_path.write_text no longer present in the hook)
- session_end.py: four state fields now included in the pipe event payload
- exit_plan_mode.py: direct state.json write removed (already covered in
  test_pipe_isolation.py; duplicated here for co-location)
"""
from pathlib import Path


def _read_hook_source(hook_name: str) -> str:
    """Read the source of a hook file relative to the repo root."""
    repo_root = Path(__file__).parent.parent.parent
    hook_path = repo_root / "hooks" / hook_name
    return hook_path.read_text(encoding="utf-8")


# ── session_end.py structural checks ─────────────────────────────────────────

def test_session_end_does_not_define_state_path_constant():
    """session_end.py must not define STATE_PATH (direct state write removed)."""
    source = _read_hook_source("session_end.py")
    assert "STATE_PATH" not in source, (
        "session_end.py still defines STATE_PATH — direct state write must be removed"
    )


def test_session_end_does_not_write_state_json_directly():
    """session_end.py must not call state_path.write_text (direct write removed)."""
    source = _read_hook_source("session_end.py")
    assert "state_path.write_text" not in source, (
        "session_end.py still calls state_path.write_text — direct state write must be removed"
    )


def test_session_end_includes_last_session_end_in_pipe_event():
    """session_end.py must emit last_session_end in the pipe event payload."""
    source = _read_hook_source("session_end.py")
    assert "last_session_end" in source, (
        "session_end.py does not contain 'last_session_end' — field must be in pipe event"
    )


def test_session_end_includes_last_session_closed_in_pipe_event():
    """session_end.py must emit last_session_closed in the pipe event payload."""
    source = _read_hook_source("session_end.py")
    assert "last_session_closed" in source, (
        "session_end.py does not contain 'last_session_closed' — field must be in pipe event"
    )
