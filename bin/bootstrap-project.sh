#!/bin/bash
# Bootstrap a new project with agent integration
# Usage: bootstrap-project.sh /path/to/new/project [project-name]
#
# Creates:
#   .memory-bank/       — Project knowledge
#   .claude/             — Claude Code config + rules + hooks

set -e

PROJECT_PATH="${1:-.}"
PROJECT_NAME="${2:-$(basename "$PROJECT_PATH")}"
TEMPLATES="$HOME/Projects/agent/templates"

echo "🚀 Bootstrapping project: $PROJECT_NAME"
echo "📁 Location: $PROJECT_PATH"
echo ""

# Check if project directory exists
if [ ! -d "$PROJECT_PATH" ]; then
    echo "❌ Error: Directory $PROJECT_PATH does not exist"
    exit 1
fi

# ============================================
# 1. MEMORY BANK (brief.md only — lightweight project identity)
# ============================================
MEMORY_BANK="$PROJECT_PATH/.memory-bank"
echo "📝 Creating .memory-bank/..."
mkdir -p "$MEMORY_BANK"

if [ ! -f "$MEMORY_BANK/brief.md" ]; then
    if [ -f "$TEMPLATES/memory-bank/brief.md" ]; then
        cp "$TEMPLATES/memory-bank/brief.md" "$MEMORY_BANK/"
    else
        cat > "$MEMORY_BANK/brief.md" << BRIEF_EOF
# Project Brief: $PROJECT_NAME

<!-- What is this project? Why does it exist? What problem does it solve? -->

## Goals
<!-- Key objectives -->

## Key Context
<!-- Important constraints, integrations, or decisions -->
BRIEF_EOF
    fi
    echo "  ✓ brief.md"
else
    echo "  ⏭ brief.md (exists)"
fi

# ============================================
# 2. CLAUDE CONFIG
# ============================================
CLAUDE_DIR="$PROJECT_PATH/.claude"
echo ""
echo "🤖 Creating .claude/..."
mkdir -p "$CLAUDE_DIR/rules"

if [ ! -f "$CLAUDE_DIR/CLAUDE.md" ]; then
    cat > "$CLAUDE_DIR/CLAUDE.md" << EOF
# Claude Code — $PROJECT_NAME

## Project Values
- **Minimal impact** — Make the smallest changes necessary. Don't over-engineer
- **No dirty state** — Don't leave the environment broken. Verify changes work before completing a task
- **Reversibility** — Ensure significant changes can be undone if needed

### Boundaries
<!-- TODO: Add project-specific boundaries -->

## Memory Bank
Auto-loaded at session start. Full files in \`.memory-bank/\`:
- \`brief.md\` — Project goals and scope

After major tasks, update brief.md if project direction has changed.

## Security
**CRITICAL**: NEVER commit, push, or expose secrets, API keys, tokens, or credentials to version control.

- NEVER hardcode secrets in code — use environment variables and \`.env\` files
- NEVER commit files containing secrets — verify with \`git diff --cached\` before committing
- ALWAYS check \`.gitignore\` has \`.env*\`, \`credentials.*\`, \`secrets.*\`, \`*.key\`, \`*.pem\`
- ASK before committing sensitive-looking files (\`config.json\`, \`.env*\`, \`credentials.*\`)
- If secrets are accidentally committed: STOP, alert user to revoke, remove from history, add to \`.gitignore\`
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
# 3. REGISTER IN HUB
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
# 4. SUMMARY
# ============================================
echo ""
echo "✅ Bootstrap complete!"
echo ""
echo "📂 Structure:"
echo "   $PROJECT_PATH/"
echo "   ├── .memory-bank/"
echo "   │   └── brief.md           (project identity — auto-loaded at session start)"
echo "   ├── .claude/"
echo "   │   ├── CLAUDE.md          (project instructions + rules)"
echo "   │   ├── settings.json      (project-specific settings)"
echo "   │   └── skills/            (add SKILL.md per workflow)"
echo ""
echo "📝 Next steps:"
echo "   1. Fill in .memory-bank/ files with project details"
echo "   2. Add skills in .claude/skills/<name>/SKILL.md for project workflows"
echo "   3. Install core plugin: claude plugin install haint-core@haint-marketplace --scope user"
echo "   4. (Godot projects) Install: claude plugin install godot-dev@haint-marketplace --scope project"
echo "   5. Run: cd $PROJECT_PATH && claude"
echo ""
