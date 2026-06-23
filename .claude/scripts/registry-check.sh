#!/bin/bash
# SessionStart hook (hub only): quick registry drift check.
# Silent on clean state; prints only genuine drift (new dir / vanished path).
# registry.json v2 = orientation catalog {path,type,summary,status?}; capability
# lists are derived on demand, so the only drift is NEW (unregistered dir) or
# STALE (registered path gone). Paths are absolute → no tilde expansion needed.

HUB="$HOME/Projects/agent"
REGISTRY="$HUB/registry.json"

[ ! -f "$REGISTRY" ] && exit 0
command -v jq &>/dev/null || exit 0

DRIFT=0
ISSUES=""

# New (unregistered) project dirs
for dir in "$HOME/Projects"/*/; do
    name=$(basename "$dir")
    registered=$(jq -r --arg n "$name" '.projects[$n] // empty' "$REGISTRY")
    [ -z "$registered" ] && ISSUES+="  NEW: $name (not registered)\n" && DRIFT=$((DRIFT + 1))
done

# Stale (registered path gone)
for name in $(jq -r '.projects | keys[]' "$REGISTRY"); do
    path=$(jq -r --arg n "$name" '.projects[$n].path' "$REGISTRY")
    path="${path/#\~/$HOME}"   # safety net for legacy ~ entries (v2 paths are absolute)
    [ ! -d "$path" ] && ISSUES+="  STALE: $name (path gone)\n" && DRIFT=$((DRIFT + 1))
done

# Narrative sync — registry primary must match what ecosystem.md / core-memory crown
if [ -f "$HUB/bin/registry-lib.sh" ]; then
    source "$HUB/bin/registry-lib.sh"
    sync_lines=$(check_narrative_sync "$REGISTRY"); rc=$?
    [ "$rc" -ne 0 ] && ISSUES+="$sync_lines\n" && DRIFT=$((DRIFT + rc))
fi

if [ "$DRIFT" -gt 0 ]; then
    echo ""
    echo "--- Registry Drift ($DRIFT) ---"
    printf "$ISSUES"
    echo "Run: bash bin/ag-registry-audit.sh"
    echo "---"
fi
