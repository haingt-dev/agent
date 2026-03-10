#!/bin/bash
# SessionStart hook: trigger /reschedule-quest once per day (first session only)

GUARD="/tmp/.claude-reschedule-$(date +%Y%m%d)"

if [ -f "$GUARD" ]; then
    exit 0
fi

touch "$GUARD"
echo ""
echo "--- Daily Reschedule ---"
echo "First session today. Run: /reschedule-quest"
echo "---"
