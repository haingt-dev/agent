#!/bin/bash
# PreToolUse safety: Block dangerous commands and sensitive file commits

INPUT="$CLAUDE_TOOL_INPUT"

# --- Block dangerous commands ---
if echo "$INPUT" | grep -qE '(rm -rf /|git push.*--force|git reset --hard|git clean -fd)'; then
    echo "BLOCKED: Dangerous command. Ask user for confirmation." >&2
    exit 2
fi

# --- Block sensitive file commits ---
if echo "$INPUT" | grep -qE 'git (add|commit)'; then
    SENSITIVE=$(git diff --cached --name-only 2>/dev/null | grep -iE '\.(env|key|pem)$|credentials|secrets' || true)
    if [ -n "$SENSITIVE" ]; then
        echo "BLOCKED: Sensitive files staged: $SENSITIVE" >&2
        exit 2
    fi
fi
