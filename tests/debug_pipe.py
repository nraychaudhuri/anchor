#!/usr/bin/env python3
"""
Run this in your project root to diagnose claude -p behavior.
python test/diagnose.py
"""
import subprocess, json, os, sys


def run(cmd, stdin_text=None):
    result = subprocess.run(cmd, input=stdin_text, capture_output=True, text=True, timeout=30)
    try:
        out = json.loads(result.stdout)
        return {
            "returncode": result.returncode,
            "result": out.get("result", ""),
            "input_tokens": out.get("usage", {}).get("input_tokens"),
            "output_tokens": out.get("usage", {}).get("output_tokens"),
            "model": list(out.get("modelUsage", {}).keys()),
            "stderr": result.stderr[:100],
        }
    except:
        return {
            "returncode": result.returncode,
            "raw": result.stdout[:300],
            "stderr": result.stderr[:100],
        }


print("=" * 60)
print("COMPANION DIAGNOSTIC")
print("=" * 60)

# 1. bare mode
print("\n1. claude -p --bare (bypasses all project context/hooks)")
r = run(["claude", "-p", "say the word hello", "--output-format", "json", "--bare"])
print(json.dumps(r, indent=2))

# 2. normal mode
print("\n2. claude -p normal mode")
r = run(["claude", "-p", "say the word hello", "--output-format", "json"])
print(json.dumps(r, indent=2))

# 3. haiku model explicitly
print("\n3. claude -p haiku model explicitly")
r = run(
    [
        "claude",
        "-p",
        "say the word hello",
        "--output-format",
        "json",
        "--model",
        "claude-haiku-4-5-20251001",
    ]
)
print(json.dumps(r, indent=2))

# 4. stdin piped
print("\n4. claude -p with stdin piped")
r = run(
    ["claude", "-p", "what words did i just give you? repeat them back", "--output-format", "json"],
    stdin_text="banana mango papaya",
)
print(json.dumps(r, indent=2))

# 5. CLAUDE.md files
print("\n5. CLAUDE.md files:")
for path in ["CLAUDE.md", "~/.claude/CLAUDE.md", ".claude/CLAUDE.md"]:
    full = os.path.expanduser(path)
    if os.path.exists(full):
        size = os.path.getsize(full)
        print(f"  EXISTS: {full} ({size} bytes)")
        with open(full) as f:
            print(f"  First 300 chars: {repr(f.read(300))}")
    else:
        print(f"  not found: {full}")

# 6. settings.json hooks
print("\n6. settings.json hooks:")
for path in [".claude/settings.json", os.path.expanduser("~/.claude/settings.json")]:
    if os.path.exists(path):
        with open(path) as f:
            try:
                s = json.load(f)
                hooks = s.get("hooks", {})
                print(f"  {path}: hooks={list(hooks.keys())}")
                # check for Stop hooks specifically
                if "Stop" in hooks:
                    print(f"    Stop hooks: {json.dumps(hooks['Stop'], indent=4)}")
            except Exception as e:
                print(f"  {path}: parse error {e}")
    else:
        print(f"  not found: {path}")

# 7. lockfile
print("\n7. Lockfile:")
lf = "/tmp/companion_extracting.lock"
if os.path.exists(lf):
    print(f"  STUCK LOCKFILE at {lf} — delete it!")
    os.remove(lf)
    print(f"  Deleted.")
else:
    print(f"  clean (no stuck lockfile)")

# 8. version
print("\n8. Claude version:")
r2 = subprocess.run(["claude", "--version"], capture_output=True, text=True)
print(f"  {r2.stdout.strip()}")

# 9. test JSON extraction directly
print("\n9. JSON extraction test (the actual use case):")
r = run(
    [
        "claude",
        "-p",
        'The order cannot be modified after confirmation. Extract this as JSON: [{"type":"business_rule","text":"..."}]. Return ONLY JSON array.',
        "--output-format",
        "json",
    ]
)
print(json.dumps(r, indent=2))

print("\n" + "=" * 60)
print("Paste all output above back into chat.")
print("=" * 60)

# 10. test with --output-format text (the fix)
print("\n10. claude -p --output-format text (the fix):")
result = subprocess.run(
    [
        "claude",
        "-p",
        'Return ONLY this JSON array with no other text: [{"color": "blue"}, {"color": "green"}]',
        "--output-format",
        "text",
    ],
    capture_output=True,
    text=True,
    timeout=30,
)
print(f"  returncode: {result.returncode}")
print(f"  stdout: {repr(result.stdout[:300])}")
print(f"  stderr: {repr(result.stderr[:100])}")
