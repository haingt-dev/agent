#!/bin/bash
# Audit registry.json (v2) against actual project state.
# Usage: ag-registry-audit
#
# registry.json (v2) is an AI/human ORIENTATION CATALOG: {path, type, summary, status?}
# per project — the facts the filesystem can't cheaply reveal. Capability lists
# (skills/plugins/rules/mcps) are DERIVED ON DEMAND (ls .claude/skills, jq .mcp.json,
# jq installed_plugins.json), NOT stored — so there is nothing there to drift.
#
# Two checks only:
#   1. Every ~/Projects/<dir> is a registry key   (else MISSING)
#   2. Every registered path exists on disk         (else STALE)

set -e

HUB="$HOME/Projects/agent"
REGISTRY="$HUB/registry.json"
PROJECTS_DIR="$HOME/Projects"
DRIFT=0

[ -f "$REGISTRY" ] || { echo "Error: $REGISTRY not found."; exit 1; }
command -v jq &>/dev/null || { echo "Error: jq required"; exit 1; }

red()    { printf "\033[31m%s\033[0m\n" "$1"; }
green()  { printf "\033[32m%s\033[0m\n" "$1"; }
yellow() { printf "\033[33m%s\033[0m\n" "$1"; }

# Safety net for any legacy hand-added ~ path (v2 stores absolute; this is a no-op on those).
expand_tilde() { printf '%s' "${1/#\~/$HOME}"; }

# 1. Unregistered project dirs
echo "=== Unregistered projects ==="
for dir in "$PROJECTS_DIR"/*/; do
    name=$(basename "$dir")
    registered=$(jq -r --arg n "$name" '.projects[$n] // empty' "$REGISTRY")
    if [ -z "$registered" ]; then
        red "  MISSING: $name (dir not in registry — register via /project-creator or add an entry)"
        DRIFT=$((DRIFT + 1))
    fi
done

# 2. Registered paths exist
echo "=== Stale registry entries ==="
for name in $(jq -r '.projects | keys[]' "$REGISTRY"); do
    path=$(expand_tilde "$(jq -r --arg n "$name" '.projects[$n].path' "$REGISTRY")")
    if [ ! -d "$path" ]; then
        red "  STALE: $name -> $path (dir gone — update path or remove the entry)"
        DRIFT=$((DRIFT + 1))
    fi
done

echo ""
if [ "$DRIFT" -eq 0 ]; then
    green "Registry in sync. No drift."
    exit 0
fi
red "Found $DRIFT drift(s)."
exit 1
