#!/bin/bash
# Session Start: Git context + Memory Bank brief
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

# --- Compact mode: brief only ---
if [ "$SOURCE" = "compact" ]; then
    if [ -f ".memory-bank/brief.md" ]; then
        echo ""
        echo "=== brief.md ==="
        head -50 ".memory-bank/brief.md"
    fi
    exit 0
fi

# --- Full mode (startup/resume): git log + brief ---
echo "Recent commits:"
git log --oneline -5 2>/dev/null || echo "(not a git repo)"
echo ""

if [ -f ".memory-bank/brief.md" ]; then
    echo "--- Memory Bank ---"
    echo "=== brief.md ==="
    head -50 ".memory-bank/brief.md"
    echo "--- End Memory Bank ---"
fi

# --- Brain: deterministic context injection ---
BRAIN_PYTHON="/home/haint/Projects/agent/mcp/haingt-brain/.venv/bin/python3"
[ -x "$BRAIN_PYTHON" ] || BRAIN_PYTHON="python3"
BRAIN_CONTEXT=$("$BRAIN_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/brain-context.py" 2>/dev/null)
if [ -n "$BRAIN_CONTEXT" ]; then
    echo ""
    echo "--- Brain Context ---"
    echo "$BRAIN_CONTEXT"
    echo "--- End Brain ---"
fi
