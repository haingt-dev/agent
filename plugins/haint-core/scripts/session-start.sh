#!/bin/bash
# Session Start: Git context + Memory Bank auto-load
# Loads ALL .memory-bank/*.md files, prioritizing brief > context > tech

# --- Git Context ---
echo "Branch: $(git branch --show-current 2>/dev/null || echo 'n/a')"
echo "Recent commits:"
git log --oneline -5 2>/dev/null || echo "(not a git repo)"
echo ""

# --- Memory Bank ---
MB_DIR=".memory-bank"

if [ ! -d "$MB_DIR" ]; then
    echo "(No .memory-bank/ found)"
    exit 0
fi

echo "--- Memory Bank ---"

# Priority files first
for f in brief.md context.md tech.md; do
    if [ -f "$MB_DIR/$f" ]; then
        echo "=== $f ==="
        head -50 "$MB_DIR/$f"
        echo ""
    fi
done

# Then any other .md files (skip already-loaded ones)
for f in "$MB_DIR"/*.md; do
    [ ! -f "$f" ] && continue
    basename_f=$(basename "$f")
    case "$basename_f" in
        brief.md|context.md|tech.md) continue ;;
    esac
    echo "=== $basename_f ==="
    head -50 "$f"
    echo ""
done

echo "--- End Memory Bank ---"
