#!/bin/bash
# Notification hook: Desktop notification via notify-send (Linux)
# Input: JSON from stdin with "message" and optional "title" fields

command -v notify-send &>/dev/null || exit 0

INPUT=$(cat)

if command -v jq &>/dev/null; then
    TITLE=$(echo "$INPUT" | jq -r '.title // "Claude Code"')
    MESSAGE=$(echo "$INPUT" | jq -r '.message // "Needs your attention"')
else
    TITLE=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('title','Claude Code'))" 2>/dev/null || echo "Claude Code")
    MESSAGE=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('message','Needs your attention'))" 2>/dev/null || echo "Needs your attention")
fi

notify-send -a "Claude Code" -i dialog-information "$TITLE" "$MESSAGE"
