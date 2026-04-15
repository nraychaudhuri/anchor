#!/usr/bin/env python3
"""Test that editing the same file 5 times shows it once in the chart."""
import json
import os
import sys
import tempfile
import shutil
from pathlib import Path

sidebar_dir = Path(__file__).parent.parent / "skills" / "companion" / "scripts"
sys.path.insert(0, str(sidebar_dir))
import sidebar

tmp_dir = Path(tempfile.mkdtemp(prefix="anchor-dedup-test-"))
companion_dir = tmp_dir / ".companion"
companion_dir.mkdir()
(companion_dir / "modules.json").write_text(json.dumps([
    {"name": "alerts", "paths": ["al/alerts/"]},
]))
os.chdir(tmp_dir)
sidebar._modules_cache = None

loaded = ["decision-ledger", "finance-twin"]
mini = sidebar.MiniSession(started_at="10:00:00")

# Edit same file 5 times
for i in range(5):
    sidebar.update_mini_session(mini, {
        "event": "post_tool_use",
        "file_path": "al/alerts/evaluator.py",
        "cwd": str(tmp_dir),
    }, loaded)

chart = sidebar.build_chart(mini, loaded)
sidebar.console.print(chart)

print(f"\nFiles in mini.files: {len(mini.files)}")
assert len(mini.files) == 1, f"Expected 1 file (deduped), got {len(mini.files)}"
print("✓ DEDUP PASSED — same file edited 5 times shows once")

shutil.rmtree(tmp_dir, ignore_errors=True)
