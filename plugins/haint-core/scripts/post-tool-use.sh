#!/bin/bash
# PostToolUse: Auto-persist research results to brain.db
# Captures: WebSearch, WebFetch, Context7 query-docs
# Falls back to text reminder if Python script fails

INPUT=$(cat)

# Route all matched tools to search-and-store.py (matcher already filters)
BRAIN_PYTHON="/home/haint/Projects/agent/mcp/haingt-brain/.venv/bin/python3"
[ -x "$BRAIN_PYTHON" ] || BRAIN_PYTHON="python3"
echo "$INPUT" | "$BRAIN_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/search-and-store.py" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Consider: brain_save this finding as type 'discovery' if it's reusable."
fi
