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

# Linux: try common terminal emulators
if [ "$(uname)" = "Linux" ] && { [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; }; then
    LAUNCHER="$SCRIPT_DIR/launch_sidebar.sh"
    if command -v gnome-terminal &>/dev/null; then
        gnome-terminal -- bash "$LAUNCHER" 2>/dev/null && echo "sidebar started in gnome-terminal" && exit 0
    fi
    if command -v konsole &>/dev/null; then
        konsole -e bash "$LAUNCHER" 2>/dev/null && echo "sidebar started in konsole" && exit 0
    fi
    if command -v xfce4-terminal &>/dev/null; then
        xfce4-terminal -e "bash \"$LAUNCHER\"" 2>/dev/null && echo "sidebar started in xfce4-terminal" && exit 0
    fi
    if command -v mate-terminal &>/dev/null; then
        mate-terminal -e "bash \"$LAUNCHER\"" 2>/dev/null && echo "sidebar started in mate-terminal" && exit 0
    fi
    if command -v tilix &>/dev/null; then
        tilix -e "bash \"$LAUNCHER\"" 2>/dev/null && echo "sidebar started in tilix" && exit 0
    fi
    if command -v alacritty &>/dev/null; then
        alacritty -e bash "$LAUNCHER" 2>/dev/null && echo "sidebar started in alacritty" && exit 0
    fi
    if command -v kitty &>/dev/null; then
        kitty bash "$LAUNCHER" 2>/dev/null && echo "sidebar started in kitty" && exit 0
    fi
    if command -v wezterm &>/dev/null; then
        wezterm start -- bash "$LAUNCHER" 2>/dev/null && echo "sidebar started in wezterm" && exit 0
    fi
    if command -v xterm &>/dev/null; then
        xterm -e bash "$LAUNCHER" 2>/dev/null && echo "sidebar started in xterm" && exit 0
    fi
fi

# fallback: background process
nohup uv run "$SIDEBAR" > "$LOGFILE" 2>&1 &
echo $! > "$PIDFILE"
echo "sidebar started in background (pid $!)"
echo "run: tail -f .companion/sidebar.log"
