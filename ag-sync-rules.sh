#!/bin/bash
# Sync shared rules to all (or one) project's agent rule directories
# Usage: ag-sync-rules [ProjectName]

set -e

TEMPLATES_DIR="$HOME/Projects/agent/templates/rules"
PROJECTS_DIR="$HOME/Projects"
RULES=("commit-protocol.md" "soul.md")

for rule in "${RULES[@]}"; do
    [ ! -f "$TEMPLATES_DIR/$rule" ] && echo "Error: $TEMPLATES_DIR/$rule not found" && exit 1
done

sync_project() {
    local name=$(basename "$1") updated=0
    for rule in "${RULES[@]}"; do
        local src="$TEMPLATES_DIR/$rule"
        for dir in .claude/rules; do
            local target="$1/$dir/$rule"
            [ -d "$1/$dir" ] && ! diff -q "$src" "$target" &>/dev/null && cp "$src" "$target" && updated=$((updated + 1))
        done
    done
    [ $updated -gt 0 ] && echo "  + $name ($updated updated)" || echo "  . $name (up to date)"
}

echo "Syncing rules: ${RULES[*]}"
if [ -n "$1" ]; then
    [ -d "$PROJECTS_DIR/$1" ] && sync_project "$PROJECTS_DIR/$1" || { echo "Error: $1 not found"; exit 1; }
else
    for p in "$PROJECTS_DIR"/*/; do [ -d "$p" ] && sync_project "$p"; done
fi
echo "Done"
