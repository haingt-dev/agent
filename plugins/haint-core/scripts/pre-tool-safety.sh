#!/bin/bash
# PreToolUse safety: Tiered command protection
# Input: JSON from stdin per hooks spec (https://code.claude.com/docs/en/hooks)
#
# Decisions:
#   deny  — hard block, no bypass (catastrophic commands)
#   ask   — show permission dialog, user can approve/deny

# --- Read stdin ---
INPUT=$(cat)

# --- Extract command (Bash tool only, matcher already filters) ---
if command -v jq &>/dev/null; then
    COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty' 2>/dev/null)
else
    COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null)
fi

[ -z "$COMMAND" ] && exit 0

# --- Helper: emit hookSpecificOutput ---
emit() {
    local decision="$1" reason="$2"
    cat <<EOF
{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"${decision}","permissionDecisionReason":"${reason}"}}
EOF
    exit 0
}

# --- Tier 1: DENY — catastrophic, no bypass ---
if echo "$COMMAND" | grep -qE 'rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+/\s*$'; then
    emit "deny" "Catastrophic: rm -rf / (root filesystem deletion)"
fi
if echo "$COMMAND" | grep -qE 'rm\s+-[a-zA-Z]*r[a-zA-Z]*f[a-zA-Z]*\s+(~|\$HOME|\$\{HOME\})\s*$'; then
    emit "deny" "Catastrophic: rm -rf ~ (home directory deletion)"
fi

# --- Tier 2: ASK — dangerous but confirmable ---
if echo "$COMMAND" | grep -qE 'rm\s+-[a-zA-Z]*r[a-zA-Z]*f'; then
    emit "ask" "Dangerous: recursive force delete"
fi
if echo "$COMMAND" | grep -qE 'git\s+push\s.*--force'; then
    emit "ask" "Dangerous: git force push"
fi
if echo "$COMMAND" | grep -qE 'git\s+reset\s+--hard'; then
    emit "ask" "Dangerous: git reset --hard (discards uncommitted changes)"
fi
if echo "$COMMAND" | grep -qE 'git\s+clean\s+-[a-zA-Z]*f'; then
    emit "ask" "Dangerous: git clean -f (removes untracked files)"
fi

# --- Sensitive file commits ---
if echo "$COMMAND" | grep -qE 'git\s+(add|commit)'; then
    SENSITIVE=$(git diff --cached --name-only 2>/dev/null | grep -iE '\.(env|key|pem)$|credentials|secrets' || true)
    if [ -n "$SENSITIVE" ]; then
        emit "ask" "Sensitive files staged: ${SENSITIVE//$'\n'/, }"
    fi
fi
