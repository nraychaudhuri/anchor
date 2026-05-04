# Design Decisions

## Session
- Resume: `claude --resume a3d48ab2-becb-4fe4-9d9d-75bce40de4d8`
- Date: 2026-04-19

## Tradeoffs

### Manual skill execution via SKILL.md reading instead of autom
**Chose:** Manual skill execution via SKILL.md reading instead of automatic plugin-driven execution in current session
**Because:** Plugin was not pre-loaded in current session; manual execution achieves identical functional result
**Accepted cost:** Requires explicit instruction-following; loses automatic context integration and plugin hooks
**Evidence:** "The plugin isn't loaded in this session, but I can read the SKILL.md and run it manually — same effect."

### Platform-specific terminal detection logic with fallback cas
**Chose:** Platform-specific terminal detection logic with fallback case in start_sidebar.sh
**Because:** Different terminal emulators available on different OSes (Terminal.app on macOS, gnome-terminal on Linux, etc.)
**Accepted cost:** Increases code complexity and ongoing maintenance burden across platforms
**Evidence:** "Create `launch_sidebar.sh` (Linux equivalent of `launch_sidebar.command`)... Update `start_sidebar.sh` to add Linux terminal detection between the macOS blocks and the fallback"

## Decisions Made

- Create Linux support for Anchor plugin and contribute changes back via PR to original public repository
  - Evidence: "Let's see if we can get it working in Linux, and if we do, I'll PR his repo and give it to him."
  - Confidence: high

- Create launch_sidebar.sh as Linux equivalent of macOS launch_sidebar.command file
  - Evidence: "Create `launch_sidebar.sh` (Linux equivalent of `launch_sidebar.command`)"
  - Confidence: high

- Add Linux terminal detection to start_sidebar.sh before fallback case
  - Evidence: "Update `start_sidebar.sh` to add Linux terminal detection between the macOS blocks and the fallback"
  - Confidence: high

- Update README to document Linux support
  - Evidence: "Now update the README to reflect Linux support"
  - Confidence: high

- Install uv as prerequisite for sidebar functionality
  - Evidence: "`uv` isn't installed. That's a prerequisite... Want me to install it? USER: yes, please do"
  - Confidence: high

- Use gnome-terminal for Linux sidebar launching ⚠️ implicit
  - Evidence: "`gnome-terminal` is available and `$DISPLAY=:0` — we can test it."
  - Confidence: high

- Push changes to private fork and open PR against original public repository
  - Evidence: "commit our changes, push to your fork, then open the PR targeting his repo"
  - Confidence: high

- Install GitHub CLI (gh) for command-line PR operations
  - Evidence: "lets install it, I'll probably need it again... gh auth login to authenticate with SSH/GPG setup"
  - Confidence: high

- Plugin flag can be combined with session resume flag: claude -c --plugin-dir
  - Evidence: "You can combine the flags: cd /mnt/work/cora && claude -c --plugin-dir /mnt/work/anchor... That resumes your last cora session with Anchor loaded."
  - Confidence: high
