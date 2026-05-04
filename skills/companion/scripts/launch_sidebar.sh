#!/bin/bash
# Linux launcher — opened by start_sidebar.sh in a new terminal window

# Find claude binary and ensure it's in PATH
CLAUDE_BIN=$(which claude 2>/dev/null)
if [ -z "$CLAUDE_BIN" ]; then
    for p in "$HOME/.nvm/versions/node"/*/bin/claude "$HOME/.local/bin/claude" /usr/local/bin/claude; do
        [ -x "$p" ] && CLAUDE_BIN="$p" && break
    done
fi
if [ -n "$CLAUDE_BIN" ]; then
    export PATH="$(dirname "$CLAUDE_BIN"):$PATH"
fi

# Ensure OAuth token exists
AUTH_FILE="$HOME/.anchor/auth.json"
TOKEN=""
if [ -f "$AUTH_FILE" ]; then
    TOKEN=$(python3 -c "import json; print(json.load(open('$AUTH_FILE')).get('oauth_token',''))" 2>/dev/null)
fi

if [ -z "$TOKEN" ]; then
    echo ""
    echo "═══════════════════════════════════════════════════"
    echo "  First-time setup: generating OAuth token"
    echo "  (uses your existing Claude subscription — no extra cost)"
    echo "═══════════════════════════════════════════════════"
    echo ""

    TOKEN=$(claude setup-token 2>&1 | python3 -c "
import json, re, sys
from datetime import datetime
from pathlib import Path
text = sys.stdin.read()
m = re.search(r'sk-ant-oat01-[A-Za-z0-9_\-]+(?:\n[A-Za-z0-9_\-]+)*', text)
if not m:
    sys.exit(1)
token = m.group(0).replace('\n', '')
auth_file = Path.home() / '.anchor' / 'auth.json'
auth_file.parent.mkdir(parents=True, exist_ok=True)
auth_file.write_text(json.dumps({'oauth_token': token, 'created_at': datetime.now().isoformat()}, indent=2))
print(token)
")

    if [ -z "$TOKEN" ]; then
        echo "Warning: could not parse token. Sidebar will start without live extraction."
    else
        echo "Token saved to $AUTH_FILE"
    fi
fi

if [ -n "$TOKEN" ]; then
    export CLAUDE_CODE_OAUTH_TOKEN="$TOKEN"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Resolve project dir: use env var if set by start_sidebar.sh, otherwise read from hashed tmp file
if [ -n "$ANCHOR_PROJECT_DIR" ]; then
    PROJECT_DIR="$ANCHOR_PROJECT_DIR"
elif [ -n "$ANCHOR_PROJECT_HASH" ]; then
    PROJECT_DIR="$(cat "/tmp/anchor_project_dir_${ANCHOR_PROJECT_HASH}" 2>/dev/null || pwd)"
else
    PROJECT_DIR="$(cat /tmp/anchor_project_dir 2>/dev/null || pwd)"
fi

cd "$PROJECT_DIR"
uv run "$SCRIPT_DIR/sidebar.py" --project-dir "$PROJECT_DIR"
