#!/usr/bin/env python3
"""
PostToolUse hook — Pair Partner + Validator roles.

Fires after every file write/edit. Thin relay only.
Sends file change event to sidebar for UML delta + spec check.
"""
import json
import os
import sys

PIPE_PATH = "/tmp/companion.pipe"
STATE_PATH = ".companion/state.json"

WATCHED_TOOLS = {"Write", "Edit", "MultiEdit"}


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    if tool_name not in WATCHED_TOOLS:
        sys.exit(0)

    if not os.path.exists(PIPE_PATH):
        sys.exit(0)

    # get file path from tool input
    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path") or tool_input.get("path") or ""

    loaded_modules = []
    try:
        state = json.loads(open(STATE_PATH).read())
        loaded_modules = state.get("last_loaded_modules", [])
    except Exception:
        pass

    try:
        fd = os.open(PIPE_PATH, os.O_WRONLY | os.O_NONBLOCK)
        event = (
            json.dumps(
                {
                    "event": "post_tool_use",
                    "tool": tool_name,
                    "file_path": file_path,
                    "loaded_modules": loaded_modules,
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
