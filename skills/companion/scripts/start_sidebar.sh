#!/bin/bash
# Start the companion sidebar.
# Tries several approaches in order of preference.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(pwd)"
SIDEBAR="$SCRIPT_DIR/sidebar.py"
PIDFILE="$PROJECT_DIR/.companion/sidebar.pid"
LOGFILE="$PROJECT_DIR/.companion/sidebar.log"

# check if already running by process name (works regardless of how it was started)
if pgrep -f "sidebar.py" > /dev/null 2>&1; then
    echo "sidebar already running"
    exit 0
fi

# also check PID file as fallback
if [ -f "$PIDFILE" ]; then
    PID=$(cat "$PIDFILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "sidebar already running (pid $PID)"
        exit 0
    fi
fi

cd "$PROJECT_DIR"

# write project dir for launch_sidebar.command (open doesn't propagate env vars)
echo "$PROJECT_DIR" > /tmp/anchor_project_dir

# macOS: open new Terminal window (no accessibility permissions needed)
if command -v open &>/dev/null && [ "$(uname)" = "Darwin" ]; then
    open -a Terminal "$SCRIPT_DIR/launch_sidebar.command" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "sidebar started in new Terminal window"
        exit 0
    fi
fi

# macOS iTerm2
if command -v osascript &>/dev/null && osascript -e 'tell application "iTerm2" to version' &>/dev/null 2>&1; then
    osascript << EOF
tell application "iTerm2"
    create window with default profile
    tell current session of current window
        write text "cd '$PROJECT_DIR' && uv run python '$SIDEBAR'"
    end tell
end tell
EOF
    echo "sidebar started in iTerm2"
    exit 0
fi

# fallback: background process
nohup uv run "$SIDEBAR" > "$LOGFILE" 2>&1 &
echo $! > "$PIDFILE"
echo "sidebar started in background (pid $!)"
echo "run: tail -f .companion/sidebar.log"
