#!/bin/bash
# PostToolUse: Auto-persist WebSearch/WebFetch results to brain.db
# Falls back to text reminder if Python script fails

INPUT=$(cat)
TOOL_NAME=""
if command -v jq &>/dev/null; then
    TOOL_NAME=$(echo "$INPUT" | jq -r '.tool_name // empty')
fi

if [[ "$TOOL_NAME" == "WebSearch" || "$TOOL_NAME" == "WebFetch" ]]; then
    BRAIN_PYTHON="/home/haint/Projects/agent/mcp/haingt-brain/.venv/bin/python3"
    [ -x "$BRAIN_PYTHON" ] || BRAIN_PYTHON="python3"
    echo "$INPUT" | "$BRAIN_PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/search-and-store.py" 2>/dev/null
    if [ $? -ne 0 ]; then
        echo "Consider: brain_save this finding as type 'discovery' if it's reusable."
    fi
fi
