---
name: anchor:seed
description: Bootstrap the Context Companion canonical spec for a product. Use this skill when the developer runs /seed or asks to bootstrap the companion, initialize the spec, seed the project spec, set up the canonical spec, or start the context companion for the first time. Also triggers when developer says things like "build the module registry", "mine my sessions", "bootstrap from existing sessions", or "set up companion for this project". This skill reads the codebase to build a module registry, mines all historical Claude Code sessions for decisions and rules, and produces a canonical OpenSpec that becomes the source of truth for all companion roles.
argument-hint: [product name]
allowed-tools: AskUserQuestion, Bash, Read, Write, Task
disable-model-invocation: true
---

# Seed Skill

## Dependencies

```bash
uv pip install -r ${CLAUDE_SKILL_DIR}/requirements.txt -q 2>/dev/null || true
```

Bootstrap the Context Companion canonical spec from scratch.

Read `references/openspec_format.md` now — it defines the spec.json format
this skill produces.

---

## Step 0 — Interactive Setup via AskUserQuestion

**Check first:** Run `cat .companion/product.json 2>/dev/null`
If it exists, use AskUserQuestion:
```
question: "Seed is already configured for [product]. What would you like to do?"
options: ["Re-seed from scratch", "Add new sessions only", "Cancel"]
```

If not configured:

### Q1 — Product name
If `$ARGUMENTS` is non-empty, use it as PRODUCT_NAME — skip this question.
Otherwise, ask:
```
question: "What is this product called?"
options: ["Other (type your product name)"]
```
Store answer as PRODUCT_NAME.

### Q2 — Related projects

Run:
```bash
for d in ~/.claude/projects/*/; do
  count=$(ls "$d"*.jsonl 2>/dev/null | wc -l | tr -d ' ')
  [ "$count" -gt 0 ] && echo "$count $d"
done
```

Build options from projects with >0 sessions. Use AskUserQuestion:
```
question: "Which projects belong to [PRODUCT_NAME]? (select all that apply)"
options: ["<path> (N sessions)", ...]
multiSelect: true
```
Store selected directory hashes as SELECTED_HASHES.

### Q3 — Spec location
```
question: "Where should the canonical spec live?"
options: [
  "[current project]/product-spec  (recommended — version control here)",
  "~/product-specs/[PRODUCT_NAME]  (global, outside any repo)",
  "Other (type a custom path)"
]
```
Store as SPEC_LOCATION.

### Confirmation
```
question: "Ready to seed [PRODUCT_NAME]?\n  Projects: N (total sessions)\n  Spec: [SPEC_LOCATION]"
options: ["Yes, start seeding", "Cancel"]
```

If yes, run setup:
```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/setup.py \
  --product "[PRODUCT_NAME]" \
  --spec-location "[SPEC_LOCATION]" \
  --project-hashes "[hash1,hash2,...]" \
  --cwd "$PWD"
```
Capture `CONFIG_PATH` from the line `CONFIG_PATH=...` in output.

---

## Step 1 — Module Discovery

Spawn a **Task subagent** with these exact instructions:

> 1. Run: `find . -maxdepth 3 -type d | grep -v node_modules | grep -v .git | grep -v __pycache__ | sort`
> 2. Read: README.md, CLAUDE.md, package.json or pyproject.toml if present
> 3. Identify 5–15 major modules. Name them lowercase-hyphenated.
> 4. Output ONLY a JSON array between ===MODULES_START=== and ===MODULES_END===:
>
> ===MODULES_START===
> [{"name": "auth", "description": "one sentence", "paths": ["src/auth/"]}]
> ===MODULES_END===

Parse the output between `===MODULES_START===` and `===MODULES_END===`.
Write the result to `.companion/modules.json` using the Write tool.

Use AskUserQuestion to confirm:
```
question: "Found these modules: [list names]. Does this look right?"
options: ["Yes, looks good", "I want to make changes"]
```
If changes needed, update `.companion/modules.json` conversationally then confirm again.

---

## Step 2 — Spec Writing (parallel)

Read `.companion/modules.json`. Tell the developer:
`Writing specs for N modules in parallel...`

For each module, spawn a **parallel Task subagent** with these exact instructions
(substitute REAL values — no placeholders):

> Read these paths: [list actual paths from module.paths]
> Analyze what this module does at the product/architecture level.
>
> Output the spec content between these EXACT markers — nothing else:
>
> ===SPEC_START===
> {
>   "module": "[actual-module-name]",
>   "summary": "2-4 sentence description of what this module owns and does. Architecture level only, no implementation details.",
>   "business_rules": [
>     "Rule stated as plain English. What the system must do.",
>     "Another rule."
>   ],
>   "non_negotiables": [
>     "Absolute constraint that must never be violated."
>   ],
>   "tradeoffs": [
>     {"decision": "What was chosen", "reason": "Why", "accepted_cost": "What was given up"}
>   ],
>   "conflicts": [],
>   "lineage": []
> }
> ===SPEC_END===
>
> Rules for content:
> - Stay at product/architecture level. No DynamoDB field names, no function signatures.
> - business_rules: what the module MUST do (behavior constraints)
> - non_negotiables: what the module must NEVER do (absolute prohibitions)
> - tradeoffs: only if you can identify a clear architectural choice with accepted cost
> - Empty arrays are fine if nothing applies.

After ALL subagents complete:
1. For each subagent output, parse JSON between `===SPEC_START===` and `===SPEC_END===`
2. Write each to disk using the Write tool:
   `[SPEC_LOCATION]/openspec/specs/[module-name]/spec.json`
3. Verify:
```bash
find [SPEC_LOCATION]/openspec/specs -name "spec.json" | sort
```
If any modules are missing, write their spec from the subagent output directly.

---

## Step 3 — Session Mining

**IMPORTANT: Run mining directly in the main agent via Bash, NOT through Task subagents.
Subagents can return before their background processes finish writing files,
causing a race condition with the reconciler. Direct Bash calls block until complete.**

Tell the developer: `Mining N sessions across M projects...`

Get all transcript paths into a variable:
```bash
uv run python -c "
import json
from pathlib import Path
config = json.loads(Path('[CONFIG_PATH]').read_text())
for p in config['projects']:
    d = Path.home() / '.claude' / 'projects' / p['hash']
    if d.exists():
        for f in sorted(d.glob('*.jsonl')):
            print(f)
" > /tmp/companion_transcripts.txt
wc -l /tmp/companion_transcripts.txt
```
(Replace [CONFIG_PATH] with the actual path from Step 0 output)

Run all sessions in one blocking Bash call:
```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/mine_sessions.py \
  [CONFIG_PATH] \
  $(cat /tmp/companion_transcripts.txt | tr '\n' ' ')
```

The script handles all sessions sequentially with retry logic built in.
It prints progress to stderr and a JSON summary to stdout when fully done.

After the command returns, verify:
```bash
find [SPEC_LOCATION]/openspec/changes -maxdepth 1 -mindepth 1 -type d | sort
```

Check the checkpoint for any failures:
```bash
uv run python -c "
import json
from pathlib import Path
cp = Path('[CONFIG_PATH]').parent / 'mined_sessions.json'
if cp.exists():
    data = json.loads(cp.read_text())
    ok      = sum(1 for v in data.values() if v.get('success'))
    short   = sum(1 for v in data.values() if v.get('reason') == 'too_short')
    failed  = sum(1 for v in data.values() if not v.get('success') and v.get('reason') == 'extraction_failed')
    print(f'Mined: {ok}  Too short: {short}  Failed: {failed}')
"
```

If there are failed sessions, re-run the same command — the checkpoint skips
already-successful sessions and retries only the failures.

---

## Step 4 — Reconcile

**Only start reconcile after confirming all mining subagents have returned.**

Tell the developer: `Reconciling session extractions into canonical specs...`

```bash
uv run python ${CLAUDE_SKILL_DIR}/scripts/reconcile.py \
  [CONFIG_PATH] \
  .companion/modules.json
```

The reconciler:
- Assigns each extracted item to its module
- Merges rules/summary into spec.json via LLM (no overwrites — intelligent merge)
- Appends lineage entries (append-only)
- Flags conflicts for developer review

---

## Step 5 — Summary

Show the developer:
```
✓ Seed complete for [PRODUCT_NAME]

Canonical spec: [SPEC_LOCATION]/openspec/specs/

Modules: N
  • [module]: N rules, N constraints, N tradeoffs, N lineage entries
  ...

Sessions mined: N (across M projects)
Conflicts: N
```

If there are conflicts, use AskUserQuestion:
```
question: "N conflicts need your decision. Review now?"
options: ["Yes, show me", "I'll review later"]
```
If yes, read `conflicts_pending.json` and walk through each conflict,
explaining the contradiction and asking the developer to decide.

Finally:
```
Next steps:
  1. git add [SPEC_LOCATION] && git commit -m "feat: initial canonical spec"
  2. The companion now reads this spec on every session start
```

---

## Error Handling

- Module subagent fails → log error, continue with other modules
- Mining batch fails → log affected session IDs, continue with other batches
- Reconcile fails → raw extractions still in `openspec/changes/`, can re-run
- AskUserQuestion timeout (60s) → fall back to asking in plain text
