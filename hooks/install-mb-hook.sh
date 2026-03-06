#!/usr/bin/env bash
# Install Memory Bank reminder hook into a project
# Usage: install-mb-hook.sh [project-path]

set -e

PROJECT_PATH="${1:-.}"

echo "🪝 Installing Memory Bank reminder hook..."
echo "📁 Project: $PROJECT_PATH"

# Check if it's a git repository
if [ ! -d "$PROJECT_PATH/.git" ]; then
    echo "❌ Error: Not a git repository"
    echo "   $PROJECT_PATH does not contain a .git directory"
    exit 1
fi

# Check if Memory Bank exists
if [ ! -d "$PROJECT_PATH/.memory-bank" ]; then
    echo "⚠️  Warning: No Memory Bank found in this project"
    echo "   The hook will still be installed, but won't be very useful"
    echo "   Run: bootstrap $(realpath "$PROJECT_PATH")"
    echo ""
    read -p "Continue anyway? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

HOOKS_DIR="$PROJECT_PATH/.git/hooks"
HOOK_FILE="$HOOKS_DIR/post-commit"

# Backup existing hook if present
if [ -f "$HOOK_FILE" ]; then
    echo "⚠️  Existing post-commit hook found"

    # Check if it already contains our hook
    if grep -q "post-commit-mb-reminder" "$HOOK_FILE"; then
        echo "✅ Memory Bank reminder already installed"
        exit 0
    fi

    BACKUP_FILE="$HOOK_FILE.backup.$(date +%s)"
    echo "📦 Backing up to: $(basename "$BACKUP_FILE")"
    cp "$HOOK_FILE" "$BACKUP_FILE"

    # Append our hook to existing one
    echo "" >> "$HOOK_FILE"
    echo "# Memory Bank Update Reminder" >> "$HOOK_FILE"
    cat "$HOME/Projects/agent/hooks/post-commit-mb-reminder" >> "$HOOK_FILE"
    echo "✅ Memory Bank reminder appended to existing hook"
else
    # Create new hook
    cp "$HOME/Projects/agent/hooks/post-commit-mb-reminder" "$HOOK_FILE"
    chmod +x "$HOOK_FILE"
    echo "✅ Memory Bank reminder hook installed"
fi

echo ""
echo "🎉 Done! The hook will remind you to update Memory Bank after significant commits."
echo ""
echo "💡 Test it: Make a commit with 'feat:' or change 5+ files"
echo "🗑️  Uninstall: rm $HOOK_FILE"
if [ -f "$BACKUP_FILE" ]; then
    echo "♻️  Restore backup: mv $BACKUP_FILE $HOOK_FILE"
fi
echo ""
