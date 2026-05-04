#!/usr/bin/env python3
"""
Stop hook — Historian role (incremental capture).

Thin relay only. No API calls. Must exit fast.
Writes event to pipe for sidebar to process.
Sidebar does the actual extraction and conflict checking.
"""
import json
import os
import sys

PIPE_PATH = "/tmp/companion.pipe"  # legacy fallback
try:
    import json as _json
    _state = _json.loads(open(".companion/state.json").read())
    if _state.get("pipe_path"):
        PIPE_PATH = _state["pipe_path"]
except Exception:
    pass
STATE_PATH = ".companion/state.json"


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    # only relay if pipe exists and someone is reading it
    if not os.path.exists(PIPE_PATH):
        sys.exit(0)

    # read mode and loaded modules from state
    mode = "planning"
    loaded_modules = []
    try:
        state = json.loads(open(STATE_PATH).read())
        mode = state.get("mode", "planning")
        loaded_modules = state.get("last_loaded_modules", [])
    except Exception:
        pass

    try:
        fd = os.open(PIPE_PATH, os.O_WRONLY | os.O_NONBLOCK)
        event = (
            json.dumps(
                {
                    "event": "stop",
                    "mode": mode,
                    "loaded_modules": loaded_modules,
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

    sys.exit(0)


if __name__ == "__main__":
    main()
