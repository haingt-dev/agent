#!/bin/bash
# Bootstrap a new project with multi-agent integration
# Usage: bootstrap-project.sh /path/to/new/project [project-name]
#
# Creates:
#   .memory-bank/       — Shared project knowledge (all agents)
#   AGENTS.md            — Shared project instructions (all agents)
#   .claude/             — Claude Code config + rules + hooks
#   .kilocode/           — Kilo Code config + rules
#   .antigravity/        — Antigravity workspace rules
#   .agent/skills/       — Antigravity workspace skills

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
# 1. MEMORY BANK (shared)
# ============================================
MEMORY_BANK="$PROJECT_PATH/.memory-bank"
echo "📝 Creating .memory-bank/..."
mkdir -p "$MEMORY_BANK"

if [ -d "$TEMPLATES/memory-bank" ]; then
    for template in "$TEMPLATES/memory-bank"/*.md; do
        if [ -f "$template" ]; then
            filename=$(basename "$template")
            if [ ! -f "$MEMORY_BANK/$filename" ]; then
                cp "$template" "$MEMORY_BANK/"
                echo "  ✓ $filename"
            else
                echo "  ⏭ $filename (exists)"
            fi
        fi
    done
else
    for file in brief product context task architecture tech; do
        [ ! -f "$MEMORY_BANK/$file.md" ] && echo "# ${file^}" > "$MEMORY_BANK/$file.md" && echo "  ✓ $file.md"
    done
fi

# Stories subdirectory (not auto-loaded by session-start)
mkdir -p "$MEMORY_BANK/stories"
if [ -f "$TEMPLATES/memory-bank/stories/index.md" ] && [ ! -f "$MEMORY_BANK/stories/index.md" ]; then
    cp "$TEMPLATES/memory-bank/stories/index.md" "$MEMORY_BANK/stories/"
    echo "  ✓ stories/index.md"
else
    echo "  ⏭ stories/index.md (exists)"
fi

# Origin story (first story for every project)
if ! ls "$MEMORY_BANK/stories/"*-origin.md &>/dev/null; then
    TODAY=$(date +%Y-%m-%d)
    ORIGIN_FILE="$MEMORY_BANK/stories/${TODAY}-origin.md"
    if [ -f "$TEMPLATES/memory-bank/stories/origin.md" ]; then
        sed "s/PROJECT_NAME/$PROJECT_NAME/g; s/YYYY-MM-DD/$TODAY/g" \
            "$TEMPLATES/memory-bank/stories/origin.md" > "$ORIGIN_FILE"
    fi
    # Append to index
    if [ -f "$MEMORY_BANK/stories/index.md" ]; then
        echo "| $TODAY | Origin: $PROJECT_NAME | origin |" >> "$MEMORY_BANK/stories/index.md"
    fi
    echo "  ✓ stories/${TODAY}-origin.md"
else
    echo "  ⏭ stories/origin (exists)"
fi

# ============================================
# 2. AGENTS.md (shared)
# ============================================
AGENTS_MD="$PROJECT_PATH/AGENTS.md"
if [ ! -f "$AGENTS_MD" ]; then
    echo ""
    echo "📋 Creating AGENTS.md..."
    cat > "$AGENTS_MD" << EOF
# $PROJECT_NAME — Project Context

> Soul & identity: see ~/.claude/CLAUDE.md or ~/.gemini/GEMINI.md

## Project Values
- **Minimal impact** — Make the smallest changes necessary. Don't over-engineer
- **No dirty state** — Don't leave the environment broken. Verify changes work before completing a task
- **Reversibility** — Ensure significant changes can be undone if needed

### Boundaries
<!-- TODO: Add project-specific boundaries -->

## Memory Bank
Auto-loaded at session start (brief, context, task, tech). Full files in \`.memory-bank/\`:
- \`brief.md\` — Project goals and scope
- \`product.md\` — Product context and constraints
- \`context.md\` — Recent changes and carry-forward notes
- \`task.md\` — Active tasks and sprint focus
- \`architecture.md\` — System architecture
- \`tech.md\` — Tech stack and tooling
- \`stories/\` — Dev stories for devlogs (not auto-loaded, use \`/story\` to capture)

After major tasks or architectural changes, update relevant Memory Bank files.

## Security
**CRITICAL**: NEVER commit, push, or expose secrets, API keys, tokens, or credentials to version control.

- NEVER hardcode secrets in code — use environment variables and \`.env\` files
- NEVER commit files containing secrets — verify with \`git diff --cached\` before committing
- ALWAYS check \`.gitignore\` has \`.env*\`, \`credentials.*\`, \`secrets.*\`, \`*.key\`, \`*.pem\`
- ASK before committing sensitive-looking files (\`config.json\`, \`.env*\`, \`credentials.*\`)
- If secrets are accidentally committed: STOP, alert user to revoke, remove from history, add to \`.gitignore\`
EOF
    echo "  ✓ AGENTS.md"
else
    echo ""
    echo "⏭ AGENTS.md (exists)"
fi

# ============================================
# 3. AGENT CONFIG (per-agent)
# ============================================

# --- Claude ---
CLAUDE_DIR="$PROJECT_PATH/.claude"
echo ""
echo "🤖 Creating .claude/..."
mkdir -p "$CLAUDE_DIR/rules"

if [ ! -f "$CLAUDE_DIR/CLAUDE.md" ]; then
    cat > "$CLAUDE_DIR/CLAUDE.md" << EOF
# Claude Code — $PROJECT_NAME

See @../AGENTS.md for shared project context.
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

# --- Kilo Code ---
echo ""
echo "🔧 Creating .kilocode/..."
mkdir -p "$PROJECT_PATH/.kilocode/rules"
echo "  ✓ Kilo Code rules directory"

# --- Antigravity ---
echo ""
echo "🌀 Creating .antigravity/..."
mkdir -p "$PROJECT_PATH/.antigravity"
mkdir -p "$PROJECT_PATH/.agent/skills"

if [ ! -f "$PROJECT_PATH/.antigravity/rules.md" ]; then
    cat > "$PROJECT_PATH/.antigravity/rules.md" << 'RULES_EOF'
# Workspace Rules

> Full project context: see AGENTS.md
> Soul & identity: see ~/.gemini/GEMINI.md

## Commit Protocol
`<type>(<scope>): <description>`

| Type | Description |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `style` | Formatting, white-space |
| `refactor` | Code change (no fix/feat) |
| `perf` | Performance improvement |
| `test` | Adding/fixing tests |
| `chore` | Build/tools maintenance |

## Context Loading
- On session start, read AGENTS.md for project context.
- Read `.memory-bank/brief.md`, `.memory-bank/context.md`, and `.memory-bank/task.md` for current state.

## Safety Guards
- NEVER run `rm -rf /`, `git reset --hard`, `git push --force` without explicit confirmation.
- NEVER commit files matching: `.env*`, `credentials.*`, `secrets.*`, `*.key`, `*.pem`.
- Before committing, verify with `git diff --cached` that no secrets are staged.
RULES_EOF
    echo "  ✓ .antigravity/rules.md"
else
    echo "  ⏭ .antigravity/rules.md (exists)"
fi
echo "  ✓ .agent/skills/ directory"

# ============================================
# 4. SUMMARY
# ============================================
echo ""
echo "✅ Bootstrap complete!"
echo ""
echo "📂 Structure:"
echo "   $PROJECT_PATH/"
echo "   ├── AGENTS.md              (shared — all agents)"
echo "   ├── .memory-bank/          (shared — project knowledge)"
echo "   │   ├── brief.md"
echo "   │   ├── product.md"
echo "   │   ├── context.md"
echo "   │   ├── task.md"
echo "   │   ├── architecture.md"
echo "   │   ├── tech.md"
echo "   │   └── stories/          (dev stories — not auto-loaded)"
echo "   ├── .claude/               (Claude Code)"
echo "   │   ├── CLAUDE.md"
echo "   │   ├── settings.json      (project-specific hooks only)"
echo "   │   └── skills/            (add SKILL.md per workflow)"
echo "   ├── .kilocode/             (Kilo Code)"
echo "   │   └── rules/"
echo "   ├── .antigravity/          (Antigravity)"
echo "   │   └── rules.md"
echo "   └── .agent/skills/         (Antigravity skills)"
echo ""
echo "📝 Next steps:"
echo "   1. Fill in .memory-bank/ files with project details"
echo "   2. Add skills in .claude/skills/<name>/SKILL.md for project workflows"
echo "   3. Install core plugin: claude plugin install haint-core@haint-marketplace --scope user"
echo "   4. (Godot projects) Install: claude plugin install godot-dev@haint-marketplace --scope project"
echo "   5. Run: cd $PROJECT_PATH && claude"
echo ""
