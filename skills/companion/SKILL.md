---
name: anchor:companion
description: Start the Context Companion for this session. Use when the developer runs /companion or wants to load project spec context, start the sidebar, or orient themselves at the beginning of a session.
allowed-tools: AskUserQuestion, Bash, Read, Write
disable-model-invocation: true
---

# Companion — Session Start

Do these things in order. No greeting. No preamble.

---

## Step 1 — Ask what to load

First, gather module suggestions:
```bash
cat .companion/modules.json 2>/dev/null || echo "[]"
```

```bash
git diff --name-only HEAD~5 2>/dev/null
```

Match changed files to module paths from modules.json to determine suggestions
(modules whose paths appear in recent git changes get the ← suggested label).

Use AskUserQuestion:
```
question: "What are we working on today?"
options: [
  "<module>  ← suggested",   (modules matching recent git files, up to 4)
  "<module>",                 (remaining modules alphabetically)
  "Nothing — start fresh"
]
multiSelect: true
```

---

## Step 1.5 — Check for unreconciled sessions

```bash
uv run python -c "
import json
from pathlib import Path
p = Path('.companion/product.json')
if not p.exists():
    print('0')
else:
    ref = json.loads(p.read_text())
    config = json.loads(Path(ref['config']).read_text())
    spec_loc = Path(config['spec_location'])
    cp_path = Path(ref['config']).parent / 'reconciled_sessions.json'
    checkpoint = json.loads(cp_path.read_text()) if cp_path.exists() else {}
    changes_dir = spec_loc / 'openspec' / 'changes'
    unreconciled = []
    if changes_dir.exists():
        for d in changes_dir.iterdir():
            if d.is_dir() and d.name not in checkpoint:
                if (d / 'incremental.json').exists():
                    unreconciled.append(d.name)
    print(len(unreconciled))
"
```

If count > 0, use AskUserQuestion:
```
question: "Found N unreconciled sessions from previous runs. Reconcile now? (merges captured decisions into your canonical spec)"
options: ["Yes, reconcile now", "Skip — I'll do it later"]
```

If yes, run reconcile:
```bash
uv run python ${CLAUDE_SKILL_DIR}/../seed/scripts/reconcile.py \
  "$(uv run python -c "import json; print(json.loads(open('.companion/product.json').read())['config'])")" \
  .companion/modules.json
```

If 0 or skip → continue to Step 2.

---

## Step 2 — Load specs and save state

**If "Nothing — start fresh" selected** → skip to Step 3.

**If modules selected:**

1. Read the spec location and existing module names:
```bash
uv run python -c "
import json
from pathlib import Path
ref = json.loads(Path('.companion/product.json').read_text())
config = json.loads(Path(ref['config']).read_text())
modules = json.loads(Path('.companion/modules.json').read_text())
module_names = [m['name'] for m in modules]
print(config['spec_location'])
print(','.join(module_names))
"
```

2. For each selected module, check if it exists in the module list.
   If a module does NOT exist, use AskUserQuestion:
```
question: "<module> doesn't exist yet. Create it as a new module?"
options: ["Yes — create it", "Skip — don't load it"]
```
   If yes, ask the user for a one-line description, then create it:
```bash
uv run python -c "
import json
from pathlib import Path
modules = json.loads(Path('.companion/modules.json').read_text())
modules.append({'name': '<module>', 'description': '<user description>', 'paths': []})
Path('.companion/modules.json').write_text(json.dumps(modules, indent=2))
# Create skeleton spec
import sys
ref = json.loads(Path('.companion/product.json').read_text())
config = json.loads(Path(ref['config']).read_text())
spec_dir = Path(config['spec_location']) / 'openspec' / 'specs' / '<module>'
spec_dir.mkdir(parents=True, exist_ok=True)
(spec_dir / 'spec.json').write_text(json.dumps({
    'module': '<module>',
    'summary': '<user description>',
    'business_rules': [],
    'non_negotiables': [],
    'tradeoffs': [],
    'conflicts': [],
    'lineage': []
}, indent=2))
print('created')
"
```

3. For each selected module read:
   `<spec_location>/openspec/specs/<module-name>/spec.json`

3. Save selected modules to state:
```bash
uv run python -c "
import json, sys
from pathlib import Path
state_path = Path('.companion/state.json')
state = json.loads(state_path.read_text()) if state_path.exists() else {}
state['last_loaded_modules'] = sys.argv[1:]
state_path.write_text(json.dumps(state, indent=2))
print('saved')
" <module1> <module2> ...
```

4. Acknowledge with one line: `Loaded: <module names>`

---

## Step 2.5 — Pairmode story context (optional)

After saving the loaded modules, check if pairmode is active:

```bash
ls .claude/settings.deny-rationale.json 2>/dev/null && echo "pairmode" || echo "no-pairmode"
```

If pairmode is active, use AskUserQuestion:
```
question: "Which story are you working on? (enter an ID like '2.3', or leave blank to skip)"
options: ["Skip"]
```

If the user provides a story ID (not "Skip" and not blank), write it to state:
```bash
uv run python -c "
import sys
from pathlib import Path
sys.path.insert(0, str(Path('${CLAUDE_SKILL_DIR}').parent.parent.parent))
from skills.pairmode.scripts.story_context import set_current_story
companion_dir = Path('.companion')
story_id = sys.argv[1]
title = sys.argv[2] if len(sys.argv) > 2 else None
set_current_story(companion_dir, story_id, title=title)
print('story context saved')
" <story-id>
```

If the user skips, do not modify state.json — the `current_story` field simply remains absent.

### state.json schema

`.companion/state.json` supports the following fields:

```json
{
  "pairmode_version": "1.0",
  "last_loaded_modules": ["module-name"],
  "current_story": {
    "id": "2.3",
    "title": "optional title",
    "set_at": "2026-04-20T00:00:00+00:00"
  }
}
```

- `last_loaded_modules` — set on every companion session start; lists the module names
  the user chose to load.
- `current_story` — **optional**; only present when the project has pairmode active and
  the user confirmed which story they are working on. Contains the story `id` (required),
  an optional `title`, and the `set_at` UTC ISO-8601 timestamp when it was recorded.
  When the user skips the prompt this field is absent and state.json is not modified.
- `pairmode_version` — set by `/anchor:pairmode bootstrap` to record which methodology
  version was used to scaffold the project.

The `story_context` helper module (`skills/pairmode/scripts/story_context.py`) provides
`set_current_story`, `get_current_story`, `clear_current_story`, `is_pairmode_active`,
`read_state`, and `write_state` for use in skills and tests.

---

## Step 3 — Start the sidebar

Now that state.json has the loaded modules, start the sidebar:

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/start_sidebar.sh
```

The sidebar will start with full context already available.

Report what it prints (started / already running).

---

Done. The spec is loaded in your context and the sidebar is watching.
