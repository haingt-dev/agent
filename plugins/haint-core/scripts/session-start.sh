#!/bin/bash
# Session Start: Git context + brain context injection
# Input: JSON from stdin with "source" field (startup|resume|compact)

# --- Read stdin ---
INPUT=$(cat)

if command -v jq &>/dev/null; then
    SOURCE=$(echo "$INPUT" | jq -r '.source // "startup"')
else
    SOURCE=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('source','startup'))" 2>/dev/null || echo "startup")
fi

# --- Git Context (always) ---
echo "Branch: $(git branch --show-current 2>/dev/null || echo 'n/a')"

# --- Commit history: full mode only. Compact already has a summary. ---
if [ "$SOURCE" != "compact" ]; then
    echo "Recent commits:"
    git log --oneline -5 2>/dev/null || echo "(not a git repo)"
fi
echo ""

# --- Brain: deterministic context injection (project anchor) ---
# SOURCE passed through: compact-mode emits hot-tier only (the compact summary
# already carries recent state — audit 2026-06-12)
BRAIN_PYTHON="/home/haint/Projects/agent/mcp/haingt-brain/.venv/bin/python3"
[ -x "$BRAIN_PYTHON" ] || BRAIN_PYTHON="python3"
BRAIN_CONTEXT=$("$BRAIN_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/brain-context.py" "$SOURCE" 2>/dev/null)
if [ -n "$BRAIN_CONTEXT" ]; then
    echo "--- Brain Context ---"
    echo "$BRAIN_CONTEXT"
    echo "--- End Brain ---"
fi
