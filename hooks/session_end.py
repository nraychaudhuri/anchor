#!/usr/bin/env python3
"""
SessionEnd hook — Historian role (deep extraction + reconcile).

Runs async so it doesn't block session exit.
Signals sidebar to do final extraction pass.
Also writes a session-end marker to state so we know this session
was properly closed (vs crashed/force-killed).
"""
import json
import os
import sys
from datetime import datetime
from pathlib import Path

PIPE_PATH = "/tmp/companion.pipe"
STATE_PATH = ".companion/state.json"


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    cwd = data.get("cwd", os.getcwd())
    session_id = data.get("session_id", "")

    # mark session as properly ended in state
    try:
        state_path = Path(cwd) / ".companion" / "state.json"
        state = {}
        if state_path.exists():
            state = json.loads(state_path.read_text())
        state["last_session_end"] = datetime.now().isoformat()
        state["last_session_id"] = session_id
        state["last_session_closed"] = True
        state["mode"] = "planning"  # reset for next session
        state_path.write_text(json.dumps(state, indent=2))
    except Exception:
        pass

    # signal sidebar to do final extraction + reconcile
    if os.path.exists(PIPE_PATH):
        try:
            fd = os.open(PIPE_PATH, os.O_WRONLY | os.O_NONBLOCK)
            event = (
                json.dumps(
                    {
                        "event": "session_end",
                        "transcript_path": data.get("transcript_path"),
                        "session_id": session_id,
                        "cwd": cwd,
                    }
                )
                + "\n"
            )
            os.write(fd, event.encode())
            os.close(fd)
        except (OSError, BlockingIOError):
            pass

    # Remind user in Claude session to close companion terminal
    print("📌 Remember to close the Anchor companion terminal.", file=sys.stderr)
    print("📌 Remember to close the Anchor companion terminal.")

    sys.exit(0)


if __name__ == "__main__":
    main()
