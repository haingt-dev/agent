#!/bin/bash
# SessionStart hook (hub only): quick registry drift check
# Runs silently on clean state, reports only drift

HUB="$HOME/Projects/agent"
REGISTRY="$HUB/registry.json"

[ ! -f "$REGISTRY" ] && exit 0
command -v jq &>/dev/null || exit 0

DRIFT=0
ISSUES=""

# Check for unregistered projects
for dir in "$HOME/Projects"/*/; do
    name=$(basename "$dir")
    [ "$name" = "agent" ] && continue
    registered=$(jq -r --arg n "$name" '.projects[$n] // empty' "$REGISTRY")
    if [ -z "$registered" ]; then
        ISSUES+="  NEW: $name (not registered)\n"
        DRIFT=$((DRIFT + 1))
    fi
done

# Quick skill/plugin drift check per registered project
for name in $(jq -r '.projects | keys[]' "$REGISTRY"); do
    path=$(jq -r --arg n "$name" '.projects[$n].path' "$REGISTRY")
    [ ! -d "$path" ] && ISSUES+="  STALE: $name (path gone)\n" && DRIFT=$((DRIFT + 1)) && continue

    # Skills drift
    registered_skills=$(jq -r --arg n "$name" '.projects[$n].skills // [] | sort | join(",")' "$REGISTRY")
    actual_skills=""
    if [ -d "$path/.claude/skills" ]; then
        actual_skills=$(find "$path/.claude/skills" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null | sort | tr '\n' ',' | sed 's/,$//')
    fi
    [ "$registered_skills" != "$actual_skills" ] && ISSUES+="  DRIFT: $name skills changed\n" && DRIFT=$((DRIFT + 1))
done

if [ "$DRIFT" -gt 0 ]; then
    echo ""
    echo "--- Registry Drift ($DRIFT) ---"
    printf "$ISSUES"
    echo "Run: bash ag-registry-audit.sh for details"
    echo "---"
fi
