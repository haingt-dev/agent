#!/bin/bash
# Session Start: Git context + Memory Bank auto-load
# Input: JSON from stdin with "source" field (startup|resume|compact)

# --- Read stdin ---
INPUT=$(cat)

if command -v jq &>/dev/null; then
    SOURCE=$(echo "$INPUT" | jq -r '.source // "startup"')
else
    SOURCE=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('source','startup'))" 2>/dev/null || echo "startup")
fi

# --- Git Context (always) ---
echo "Branch: $(git branch --show-current 2>/dev/null || echo 'n/a')"

# --- Compact mode: brief context only ---
if [ "$SOURCE" = "compact" ]; then
    MB_DIR=".memory-bank"
    if [ -f "$MB_DIR/brief.md" ]; then
        echo ""
        echo "=== brief.md ==="
        head -50 "$MB_DIR/brief.md"
    fi
    exit 0
fi

# --- Full mode (startup/resume): git log + full memory bank ---
echo "Recent commits:"
git log --oneline -5 2>/dev/null || echo "(not a git repo)"
echo ""

MB_DIR=".memory-bank"

if [ ! -d "$MB_DIR" ]; then
    echo "(No .memory-bank/ found)"
    exit 0
fi

echo "--- Memory Bank ---"

# Priority files first
for f in brief.md context.md task.md tech.md; do
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
        brief.md|context.md|task.md|tech.md) continue ;;
    esac
    echo "=== $basename_f ==="
    head -50 "$f"
    echo ""
done

echo "--- End Memory Bank ---"
