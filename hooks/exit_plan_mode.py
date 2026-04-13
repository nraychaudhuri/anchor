#!/usr/bin/env python3
"""
PermissionRequest hook — matcher: ExitPlanMode
Relays plan content to companion sidebar for impact analysis.
Does NOT auto-approve — lets Claude Code show the normal plan approval UI.
"""
import json
import os
import sys
import tempfile

PIPE_PATH = os.path.join(tempfile.gettempdir(), "companion.pipe")
STATE_PATH = ".companion/state.json"


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return

    # flip mode to implementation
    try:
        with open(STATE_PATH) as f:
            state = json.load(f)
        state["mode"] = "implementation"
        with open(STATE_PATH, "w") as f:
            json.dump(state, f, indent=2)
    except Exception:  # nosec B110
        pass

    # grab plan content from tool_input + loaded modules from state
    tool_input = data.get("tool_input", {}) or {}
    plan = (tool_input.get("plan", "") or "")[:20000]

    loaded_modules = []
    try:
        with open(STATE_PATH) as f:
            loaded_modules = json.load(f).get("last_loaded_modules", [])
    except Exception:  # nosec B110
        pass

    # signal companion: do the deep extraction pass now
    if os.path.exists(PIPE_PATH):
        try:
            fd = os.open(PIPE_PATH, os.O_WRONLY | os.O_NONBLOCK)
            event = (
                json.dumps(
                    {
                        "event": "exit_plan_mode",
                        "transcript_path": data.get("transcript_path"),
                        "session_id": data.get("session_id"),
                        "cwd": data.get("cwd"),
                        "plan": plan,
                        "loaded_modules": loaded_modules,
                    }
                )
                + "\n"
            )
            os.write(fd, event.encode())
            os.close(fd)
        except (OSError, BlockingIOError):
            pass

    # Don't output a decision — let Claude Code show the normal plan approval UI


if __name__ == "__main__":
    main()
