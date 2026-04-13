#!/usr/bin/env python3
"""Reproduce the sequential SDK call hang in sidebar conditions.

Conditions that match the real sidebar:
- Named pipe open in main thread
- call_claude invoked from worker threads (daemon)
- Multiple calls in sequence
"""
import json
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

auth_file = Path.home() / ".anchor" / "auth.json"
os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = json.loads(auth_file.read_text())["oauth_token"]

sidebar_dir = Path(__file__).parent.parent / "skills" / "companion" / "scripts"
sys.path.insert(0, str(sidebar_dir))
import sidebar

# Create pipe like sidebar does
pipe_path = tempfile.mktemp(suffix=".test-pipe")
os.mkfifo(pipe_path)


def pipe_writer(n_events: int, delay: float = 2.0):
    """Simulate hook events arriving every few seconds."""
    time.sleep(0.5)  # let pipe reader open
    for i in range(n_events):
        with open(pipe_path, "w") as p:
            p.write(json.dumps({"event": "test", "n": i}) + "\n")
        print(f"[writer] sent event {i}")
        time.sleep(delay)


def call_in_thread(call_num: int):
    """Call sidebar.call_claude from a daemon thread."""
    print(f"\n[call {call_num}] starting call_claude...")
    start = time.time()
    result = sidebar.call_claude("Say hello briefly", "Reply in 5 words.")
    elapsed = time.time() - start
    print(f"[call {call_num}] completed in {elapsed:.1f}s: {result!r}")


# Start pipe writer in background
threading.Thread(target=pipe_writer, args=(3, 3.0), daemon=True).start()

print("=== Reading pipe, spawning call_claude on each event ===")
try:
    while True:
        with open(pipe_path) as pipe:
            for line in pipe:
                line = line.strip()
                if not line:
                    continue
                event = json.loads(line)
                print(f"\n[main] got event: {event}")
                t = threading.Thread(target=call_in_thread, args=(event["n"],), daemon=True)
                t.start()
                # Wait for it to complete (with timeout)
                t.join(timeout=30)
                if t.is_alive():
                    print(f"[main] call {event['n']} HUNG after 30s")
                    break
            else:
                continue
            break
except KeyboardInterrupt:
    pass
finally:
    os.unlink(pipe_path)
    print("\n=== done ===")
