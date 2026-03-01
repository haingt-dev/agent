#!/bin/bash
# PreToolUse safety: Block dangerous commands and sensitive file commits
# Input: JSON from stdin per hooks spec (https://code.claude.com/docs/en/hooks)

# --- Read stdin ---
INPUT=$(cat)

# --- Extract command (Bash tool only, matcher already filters) ---
if command -v jq &>/dev/null; then
    COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')
else
    COMMAND=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('command',''))" 2>/dev/null)
fi

[ -z "$COMMAND" ] && exit 0

# --- Block dangerous commands ---
if echo "$COMMAND" | grep -qE '(rm -rf /|git push.*--force|git reset --hard|git clean -fd)'; then
    cat <<'EOF'
{"decision":"block","reason":"Dangerous command detected. Ask user for explicit confirmation before proceeding."}
EOF
    exit 0
fi

# --- Block sensitive file commits ---
if echo "$COMMAND" | grep -qE 'git (add|commit)'; then
    SENSITIVE=$(git diff --cached --name-only 2>/dev/null | grep -iE '\.(env|key|pem)$|credentials|secrets' || true)
    if [ -n "$SENSITIVE" ]; then
        cat <<EOF
{"decision":"block","reason":"Sensitive files staged: ${SENSITIVE//$'\n'/, }"}
EOF
        exit 0
    fi
fi
