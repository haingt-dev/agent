#!/bin/bash
# PreCompact: Structured snapshot to brain.db before compaction
# Uses brain venv Python for consistency; falls back to system Python

BRAIN_PYTHON="/home/haint/Projects/agent/mcp/haingt-brain/.venv/bin/python3"
if [ -x "$BRAIN_PYTHON" ]; then
    PYTHON="$BRAIN_PYTHON"
else
    PYTHON="python3"
fi

INPUT=$(cat)
echo "$INPUT" | "$PYTHON" "${CLAUDE_PLUGIN_ROOT}/scripts/pre-compact-snapshot.py" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Context approaching limit. Use brain_save for any unsaved decisions/discoveries before compaction."
fi
