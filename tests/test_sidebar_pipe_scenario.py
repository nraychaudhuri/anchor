#!/usr/bin/env python3
"""Test call_claude while a named pipe is open (mimics the exact sidebar scenario)."""
import json
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

# Load token
auth_file = Path.home() / ".anchor" / "auth.json"
token = json.loads(auth_file.read_text()).get("oauth_token", "")
os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = token
print(f"Token: {token[:20]}... | claude: {shutil.which('claude')}")

# Import sidebar
sidebar_dir = Path(__file__).parent.parent / "skills" / "companion" / "scripts"
sys.path.insert(0, str(sidebar_dir))
from sidebar import call_claude

# Create a named pipe (like sidebar does)
pipe_path = tempfile.mktemp(suffix=".pipe")
os.mkfifo(pipe_path)
print(f"Created pipe: {pipe_path}")

result = {"value": None, "error": None, "done": False}


def llm_worker():
    try:
        print("  [thread] calling call_claude...")
        result["value"] = call_claude(prompt="Say hello", system="Reply in 5 words.")
        print(f"  [thread] got: {result['value']!r}")
    except Exception as e:
        import traceback
        result["error"] = traceback.format_exc()
    finally:
        result["done"] = True


def pipe_writer():
    # Write to the pipe so the main thread's open() doesn't block forever
    time.sleep(0.5)
    with open(pipe_path, "w") as p:
        p.write("trigger\n")
        p.flush()


print("\n--- Opening pipe in main thread (blocks until writer connects) ---")
threading.Thread(target=pipe_writer, daemon=True).start()

with open(pipe_path) as pipe:
    print("  pipe opened, reading first line...")
    pipe.readline()
    print("  got first line, now spawning LLM thread while pipe is still open...")

    # Spawn the LLM worker while the pipe is still open (mimics sidebar)
    t = threading.Thread(target=llm_worker)
    t.start()
    t.join(timeout=40)

if t.is_alive():
    print("HUNG: thread did not complete in 40s")
elif result["error"]:
    print(f"ERROR:\n{result['error']}")
else:
    print(f"SUCCESS: {result['value']!r}")

os.unlink(pipe_path)
