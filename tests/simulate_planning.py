#!/usr/bin/env python3
"""
Test harness for planning phase companion.
Simulates Claude Code hook events without needing a real session.
Run companion sidebar in one terminal, run this in another.

Usage:
  Terminal 1: python3 .companion/sidebar.py
  Terminal 2: python3 test/simulate_planning.py
"""
import json
import os
import time
import tempfile
from pathlib import Path

PIPE_PATH = "/tmp/companion.pipe"


def write_to_pipe(event):
    """Write an event to the companion pipe."""
    if not os.path.exists(PIPE_PATH):
        print(f"Pipe not found at {PIPE_PATH}. Is sidebar.py running?")
        return False
    try:
        fd = os.open(PIPE_PATH, os.O_WRONLY | os.O_NONBLOCK)
        os.write(fd, (json.dumps(event) + "\n").encode())
        os.close(fd)
        return True
    except Exception as e:
        print(f"Failed to write to pipe: {e}")
        return False


def create_fake_transcript(messages):
    """Write a fake JSONL transcript file."""
    tf = tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False)
    for msg in messages:
        tf.write(json.dumps({"type": "message", "message": msg}) + "\n")
    tf.close()
    return tf.name


# ─────────────────────────────────────────────
# Simulated planning conversation
# ─────────────────────────────────────────────

PLANNING_CONVERSATION = [
    {
        "role": "user",
        "content": "I want to build an order processing service. Let's plan this out.",
    },
    {
        "role": "assistant",
        "content": "Great. Let's start with the core domain model. An order goes through states: pending, confirmed, processing, shipped, delivered. Once an order is confirmed we should treat it as immutable — no modifications allowed after that point. This keeps our event log clean and prevents race conditions.",
    },
    {"role": "user", "content": "Agreed. What about the payment service integration?"},
    {
        "role": "assistant",
        "content": "I'd recommend keeping payment processing fully decoupled from order management. The order service should never call the payment service directly — instead it should emit events that the payment service subscribes to. This avoids tight coupling and lets us swap payment providers.",
    },
    {"role": "user", "content": "Makes sense. Should we use GraphQL for the API layer?"},
    {
        "role": "assistant",
        "content": "I'd actually recommend against GraphQL here. The team isn't familiar with it and it adds significant complexity — schema stitching, N+1 query problems, tooling overhead. Given we have well-defined endpoints and a tight deadline, REST is the right call. We could revisit GraphQL in a future iteration if query flexibility becomes important.",
    },
    {
        "role": "user",
        "content": "Yeah you're right, let's go with REST. What about consistency model?",
    },
    {
        "role": "assistant",
        "content": "Given the decoupled architecture with event-driven integration, we'll have eventual consistency between services. For example, when an order is confirmed, the inventory service might take a few seconds to reflect the reservation. We need to accept that reads across service boundaries may be slightly stale — up to 5 seconds in normal operation. The tradeoff is simpler architecture and better resilience versus strict consistency.",
    },
    {"role": "user", "content": "That's acceptable. Let's go with that."},
]


def simulate():
    print("─" * 50)
    print("Companion planning phase test harness")
    print("─" * 50)
    print()

    # build transcript incrementally
    messages_so_far = []

    for i, message in enumerate(PLANNING_CONVERSATION):
        messages_so_far.append(message)

        # only fire Stop after assistant messages
        if message["role"] != "assistant":
            print(f"[user]    {message['content'][:60]}...")
            time.sleep(0.5)
            continue

        print(f"[agent]   {message['content'][:60]}...")

        # write transcript so far
        transcript_path = create_fake_transcript(messages_so_far)

        # simulate Stop hook firing
        event = {
            "event": "stop",
            "transcript_path": transcript_path,
            "session_id": "test-session-001",
            "cwd": os.getcwd(),
        }

        if write_to_pipe(event):
            print(f"          → Stop hook fired, companion extracting...")

        # pause between messages — gives extraction time to run
        time.sleep(4)
        print()

    # simulate ExitPlanMode
    print()
    print("─" * 50)
    print("Developer approves plan → ExitPlanMode fires")
    print("─" * 50)

    final_transcript = create_fake_transcript(PLANNING_CONVERSATION)
    event = {
        "event": "exit_plan_mode",
        "transcript_path": final_transcript,
        "session_id": "test-session-001",
        "cwd": os.getcwd(),
    }

    if write_to_pipe(event):
        print("→ Deep extraction running in companion...")

    print()
    print("Test complete. Check sidebar for captures.")
    print("OpenSpec draft will appear in .companion/")


if __name__ == "__main__":
    simulate()
