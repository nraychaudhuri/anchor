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

## Step 2 — Load specs and save state

**If "Nothing — start fresh" selected** → skip to Step 3.

**If modules selected:**

1. Read the spec location:
```bash
uv run python -c "
import json
from pathlib import Path
ref = json.loads(Path('.companion/product.json').read_text())
config = json.loads(Path(ref['config']).read_text())
print(config['spec_location'])
"
```

2. For each selected module read:
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

## Step 3 — Start the sidebar

Now that state.json has the loaded modules, start the sidebar:

```bash
bash ${CLAUDE_SKILL_DIR}/scripts/start_sidebar.sh
```

The sidebar will start with full context already available.

Report what it prints (started / already running).

---

Done. The spec is loaded in your context and the sidebar is watching.
