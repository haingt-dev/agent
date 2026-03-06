#!/usr/bin/env bash
# Install Memory Bank reminder hook to all projects
# Usage: install-all-projects.sh

echo "🚀 Installing Memory Bank hooks to all projects..."
echo ""

INSTALLED=0
SKIPPED=0
FAILED=0

# Install to all projects in ~/Projects/
for project in ~/Projects/*/; do
    if [ -d "$project/.git" ]; then
        PROJECT_NAME=$(basename "$project")
        echo "📦 $PROJECT_NAME"

        if ~/Projects/agent/hooks/install-mb-hook.sh "$project" > /dev/null 2>&1; then
            echo "   ✅ Installed"
            INSTALLED=$((INSTALLED + 1))
        else
            echo "   ❌ Failed"
            FAILED=$((FAILED + 1))
        fi
    else
        echo "⏭  $(basename "$project") - Not a git repo"
        SKIPPED=$((SKIPPED + 1))
    fi
done

# Install to Obsidian vault if it's a git repo
if [ -d ~/Projects/Idea_Vault/.git ]; then
    echo "📦 Idea_Vault"
    if ~/Projects/agent/hooks/install-mb-hook.sh ~/Projects/Idea_Vault > /dev/null 2>&1; then
        echo "   ✅ Installed"
        INSTALLED=$((INSTALLED + 1))
    else
        echo "   ❌ Failed"
        FAILED=$((FAILED + 1))
    fi
fi

echo ""
echo "╔════════════════════════════════════╗"
echo "║         INSTALLATION SUMMARY       ║"
echo "╚════════════════════════════════════╝"
echo "  ✅ Installed: $INSTALLED"
echo "  ⏭  Skipped:   $SKIPPED"
echo "  ❌ Failed:    $FAILED"
echo ""

if [ "$FAILED" -gt 0 ]; then
    echo "⚠️  Some installations failed. Check the output above."
    exit 1
fi

echo "🎉 All projects configured!"
echo ""
