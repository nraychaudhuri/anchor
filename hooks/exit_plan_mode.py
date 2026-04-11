#!/usr/bin/env python3
"""
PermissionRequest hook — matcher: ExitPlanMode
Flips mode to implementation. Signals companion for deep extraction pass.
Approves ExitPlanMode so developer isn't blocked.
Deep extraction runs async in companion process.
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
        approve()
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
                    }
                )
                + "\n"
            )
            os.write(fd, event.encode())
            os.close(fd)
        except (OSError, BlockingIOError):
            pass

    # approve immediately — don't block developer
    approve()


def approve():
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PermissionRequest",
                    "decision": {"behavior": "allow"},
                }
            }
        )
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
