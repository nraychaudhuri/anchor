# Pipe Architecture — Project-Scoped Pipe Design

This document explains the anchor hook pipe: the original single-pipe design, why this
fork changed it, the backwards-compatibility guarantee, and which core files were modified.

---

## 1. Original design

The upstream anchor repo uses a single hardcoded pipe path: `/tmp/companion.pipe`.
All hook scripts write to this path. The companion sidebar reads from it.
This works correctly when one anchor project is active on a machine at a time.

---

## 2. The multi-project problem

When two Claude Code projects are open simultaneously — both with anchor active — their
hook scripts both write to `/tmp/companion.pipe`. Sidebar A processes messages from both
projects. Sidebar B also processes both. Decisions from project A get recorded into
project B's spec, and vice versa. This is a silent data corruption scenario.

---

## 3. Fork change: project-scoped pipe path

This fork changes the pipe path to be project-scoped. At startup, each hook script
reads the pipe path from `.companion/state.json["pipe_path"]`. If that key is absent
(legacy projects without a `state.json`), hooks fall back to `/tmp/companion.pipe`.

The pipe path stored in `state.json` is:

```python
f"/tmp/companion-{hashlib.md5(str(project_dir).encode()).hexdigest()[:8]}.pipe"
```

Each project gets a unique, deterministic pipe name. Two projects open simultaneously
use different pipes; their sidebars never cross-contaminate.

---

## 4. Backwards-compatibility

The fallback to `/tmp/companion.pipe` when `state.json` is absent means the change is
backwards-compatible for any project that has not yet run `/anchor:companion` to
establish a `state.json`. Such projects behave exactly as before.

---

## 5. Files changed in anchor core (hook + companion layer)

This is the complete list of core files touched by the pipe-scoping change:

| File | Change |
|------|--------|
| `hooks/stop.py` | Pipe path read from `state.json["pipe_path"]` at startup; falls back to `/tmp/companion.pipe` |
| `hooks/post_tool_use.py` | Same |
| `hooks/exit_plan_mode.py` | Same |
| `hooks/session_end.py` | Same |
| `skills/companion/scripts/sidebar.py` | Computes the per-project pipe hash and writes `pipe_path` into `.companion/state.json` at startup so hooks can read it back |
| `skills/companion/scripts/start_sidebar.sh`, `launch_sidebar.sh`, `launch_sidebar.command` | Pass `--project-dir` and use the hashed temp file path so the project directory survives across env boundaries (e.g. macOS `open`) |

For the complete list of all anchor-core file changes (including non-pipe pairmode work
such as the SessionStart hook and `current_story` state field), see the table in
`docs/pairmode/PAIRMODE.md` under "What pairmode changed in anchor core".

---

## 6. Alternative approaches and upstream negotiation

If the upstream maintainer has a different multi-project strategy in progress, the
narrowest compatible change is: read pipe path from an env variable
(e.g., `ANCHOR_PIPE_PATH`) with fallback to `/tmp/companion.pipe`. This would require
the companion skill to set the env variable at session start, without modifying `state.json`.
Either approach achieves the same goal; the state.json approach was chosen because the
companion skill already writes `state.json` at startup and does not require shell
environment plumbing.
