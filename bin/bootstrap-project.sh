#!/bin/bash
# Bootstrap a new project with agent integration
# Usage: bootstrap-project.sh /path/to/new/project [project-name]
#
# Creates:
#   .claude/             — Claude Code config + rules + hooks
# Project context lives in .claude/CLAUDE.md (stable) + haingt-brain (dynamic).

set -e

PROJECT_PATH="${1:-.}"
PROJECT_NAME="${2:-$(basename "$PROJECT_PATH")}"

echo "🚀 Bootstrapping project: $PROJECT_NAME"
echo "📁 Location: $PROJECT_PATH"
echo ""

# Check if project directory exists
if [ ! -d "$PROJECT_PATH" ]; then
    echo "❌ Error: Directory $PROJECT_PATH does not exist"
    exit 1
fi

# ============================================
# 1. CLAUDE CONFIG
# ============================================
CLAUDE_DIR="$PROJECT_PATH/.claude"
echo "🤖 Creating .claude/..."
mkdir -p "$CLAUDE_DIR/rules"

if [ ! -f "$CLAUDE_DIR/CLAUDE.md" ]; then
    cat > "$CLAUDE_DIR/CLAUDE.md" << EOF
# Claude Code — $PROJECT_NAME

## What Is This
<!-- 2-3 sentences: purpose, stack, goal. This is the stable project anchor. -->

## Values
<!-- Project-specific working principles. Delete if none. -->

## Context Sources
- This file (\`CLAUDE.md\`) — project identity, scope, conventions (stable anchor)
- **haingt-brain** — dynamic context (\`brain_recall\` at session start, \`brain_save\` after major work)

## Rules
<!-- Project-specific rules. Delete if none. Secrets/dangerous-command enforcement is handled by haint-core PreToolUse hook — do not duplicate here. -->
EOF
    echo "  ✓ CLAUDE.md"
else
    echo "  ⏭ CLAUDE.md (exists)"
fi

# Claude skills directory
mkdir -p "$CLAUDE_DIR/skills"
echo "  ✓ skills/ directory"

# Claude settings (hooks handled by haint-core plugin)
if [ ! -f "$CLAUDE_DIR/settings.json" ]; then
    echo '{}' > "$CLAUDE_DIR/settings.json"
    echo "  ✓ settings.json (hooks via haint-core plugin)"
else
    echo "  ⏭ settings.json (exists)"
fi

# ============================================
# 2. REGISTER IN HUB
# ============================================
REGISTRY="$HOME/Projects/agent/registry.json"
if [ -f "$REGISTRY" ] && command -v jq &>/dev/null; then
    existing=$(jq -r --arg n "$PROJECT_NAME" '.projects[$n] // empty' "$REGISTRY")
    if [ -z "$existing" ]; then
        # Detect project type
        PROJECT_TYPE="app"
        [ -f "$PROJECT_PATH/project.godot" ] && PROJECT_TYPE="godot"
        [ -f "$PROJECT_PATH/docker-compose.yml" ] || [ -f "$PROJECT_PATH/docker-compose.yaml" ] && PROJECT_TYPE="infra"
        [ -f "$PROJECT_PATH/Dockerfile" ] && [ "$PROJECT_TYPE" = "app" ] && PROJECT_TYPE="infra"

        REAL_PATH=$(cd "$PROJECT_PATH" && pwd)
        jq --arg name "$PROJECT_NAME" \
           --arg path "$REAL_PATH" \
           --arg type "$PROJECT_TYPE" \
           '.projects[$name] = {
               "path": $path,
               "type": $type,
               "status": "active",
               "bootstrapped": true,
               "plugins": [],
               "rules": [],
               "mcps": [],
               "skills": [],
               "notes": ""
           }' "$REGISTRY" > "$REGISTRY.tmp" && mv "$REGISTRY.tmp" "$REGISTRY"
        echo ""
        echo "📋 Registered in hub registry (type: $PROJECT_TYPE)"
    else
        # Update bootstrapped flag if needed
        jq --arg name "$PROJECT_NAME" '.projects[$name].bootstrapped = true' "$REGISTRY" > "$REGISTRY.tmp" && mv "$REGISTRY.tmp" "$REGISTRY"
        echo ""
        echo "📋 Registry entry exists (updated bootstrapped=true)"
    fi
else
    echo ""
    echo "⚠️  Registry not found or jq missing — skipping registration"
fi

# ============================================
# 3. SUMMARY
# ============================================
echo ""
echo "✅ Bootstrap complete!"
echo ""
echo "📂 Structure:"
echo "   $PROJECT_PATH/"
echo "   └── .claude/"
echo "       ├── CLAUDE.md          (project identity + instructions + rules)"
echo "       ├── settings.json      (project-specific settings)"
echo "       └── skills/            (add SKILL.md per workflow)"
echo ""
echo "📝 Next steps:"
echo "   1. Fill in .claude/CLAUDE.md (What Is This + project-specific rules)"
echo "   2. Add skills in .claude/skills/<name>/SKILL.md for project workflows"
echo "   3. Install core plugin: claude plugin install haint-core@haint-marketplace --scope user"
echo "   4. (Godot projects) Install: claude plugin install godot-dev@haint-marketplace --scope project"
echo "   5. Run: cd $PROJECT_PATH && claude"
echo ""
