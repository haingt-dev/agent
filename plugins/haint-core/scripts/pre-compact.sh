#!/bin/bash
# PreCompact: Snapshot conversation to brain.db before compaction
# Falls back to text reminder if Python script fails

INPUT=$(cat)
echo "$INPUT" | python3 "${CLAUDE_PLUGIN_ROOT}/scripts/pre-compact-snapshot.py" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Context approaching limit. Use brain_save for any unsaved decisions/discoveries before compaction."
fi
