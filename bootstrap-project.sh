#!/bin/bash
# Bootstrap a new project with multi-agent integration
# Usage: bootstrap-project.sh /path/to/new/project [project-name]
#
# Creates:
#   .memory-bank/       — Shared project knowledge (all agents)
#   AGENTS.md            — Shared project instructions (all agents)
#   .claude/             — Claude Code config + rules + hooks
#   .kilocode/           — Kilo Code config + rules
#   .agents/             — Antigravity config + rules

set -e

PROJECT_PATH="${1:-.}"
PROJECT_NAME="${2:-$(basename "$PROJECT_PATH")}"
TEMPLATES="$HOME/.agent_global/templates"

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
    for file in brief product context architecture tech; do
        [ ! -f "$MEMORY_BANK/$file.md" ] && echo "# ${file^}" > "$MEMORY_BANK/$file.md" && echo "  ✓ $file.md"
    done
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

> Soul & identity: see global ~/.claude/CLAUDE.md

## Project Values
- **Minimal impact** — Make the smallest changes necessary. Don't over-engineer
- **No dirty state** — Don't leave the environment broken. Verify changes work before completing a task
- **Reversibility** — Ensure significant changes can be undone if needed

### Boundaries
<!-- TODO: Add project-specific boundaries -->

## Memory Bank
Auto-loaded at session start (brief, context, tech). Full files in \`.memory-bank/\`:
- \`brief.md\` — Project goals and scope
- \`product.md\` — Product context and constraints
- \`context.md\` — Current focus and recent changes
- \`architecture.md\` — System architecture
- \`tech.md\` — Tech stack and tooling

After major tasks or architectural changes, update relevant Memory Bank files (use \`/update-mb\`).

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
# 3. AGENT RULES (per-agent)
# ============================================

# Shared commit-protocol rule content
COMMIT_PROTOCOL='# Commit Message Format
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
| `chore` | Build/tools maintenance |'

# Helper function to create rules for an agent
create_agent_rules() {
    local agent_dir="$1"
    local agent_name="$2"
    local rules_dir="$agent_dir/rules"

    mkdir -p "$rules_dir"

    if [ ! -f "$rules_dir/commit-protocol.md" ]; then
        echo "$COMMIT_PROTOCOL" > "$rules_dir/commit-protocol.md"
    fi

    # Copy soul.md from templates if available
    local soul_src="$TEMPLATES/rules/soul.md"
    if [ -f "$soul_src" ] && [ ! -f "$rules_dir/soul.md" ]; then
        cp "$soul_src" "$rules_dir/soul.md"
    fi

    echo "  ✓ $agent_name rules (commit-protocol.md, soul.md)"
}

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

# Claude commit-protocol with frontmatter
if [ ! -f "$CLAUDE_DIR/rules/commit-protocol.md" ]; then
    cat > "$CLAUDE_DIR/rules/commit-protocol.md" << 'EOF'
---
description: Commit message format and conventions
---

# Commit Message Format
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
EOF
    echo "  ✓ Claude rules (commit-protocol.md)"
fi

# Claude skills directory
mkdir -p "$CLAUDE_DIR/skills"
echo "  ✓ skills/ directory"

# Claude hooks (SessionStart + PreToolUse safety)
if [ ! -f "$CLAUDE_DIR/settings.json" ]; then
    cat > "$CLAUDE_DIR/settings.json" << 'HOOKEOF'
{
  "hooks": {
    "SessionStart": [
      {
        "matcher": "",
        "hooks": [
          {
            "type": "command",
            "command": "echo \"Branch: $(git branch --show-current 2>/dev/null || echo 'n/a')\" && echo \"Recent commits:\" && git log --oneline -5 2>/dev/null && echo '' && echo '--- Memory Bank ---' && for f in .memory-bank/brief.md .memory-bank/context.md .memory-bank/tech.md; do [ -f \"$f\" ] && echo \"=== $(basename $f) ===\" && head -50 \"$f\" && echo ''; done && echo '--- End Memory Bank ---' || true",
            "timeout": 15
          }
        ]
      }
    ],
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "if echo \"$CLAUDE_TOOL_INPUT\" | grep -qE '(rm -rf /|git push.*--force|git reset --hard|git clean -fd)'; then echo 'BLOCKED: Dangerous command. Ask user for confirmation.' >&2; exit 2; fi && if echo \"$CLAUDE_TOOL_INPUT\" | grep -qE 'git (add|commit)'; then SENSITIVE=$(git diff --cached --name-only 2>/dev/null | grep -iE '\\.(env|key|pem)$|credentials|secrets' || true); if [ -n \"$SENSITIVE\" ]; then echo \"BLOCKED: Sensitive files staged: $SENSITIVE\" >&2; exit 2; fi; fi",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
HOOKEOF
    echo "  ✓ Claude hooks (SessionStart, PreToolUse)"
else
    echo "  ⏭ Claude hooks (settings.json exists)"
fi

# --- Kilo Code ---
echo ""
echo "🔧 Creating .kilocode/..."
create_agent_rules "$PROJECT_PATH/.kilocode" "Kilo Code"

# --- Antigravity ---
echo ""
echo "🌀 Creating .agents/..."
create_agent_rules "$PROJECT_PATH/.agents" "Antigravity"

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
echo "   │   ├── architecture.md"
echo "   │   └── tech.md"
echo "   ├── .claude/               (Claude Code)"
echo "   │   ├── CLAUDE.md"
echo "   │   ├── settings.json      (hooks: SessionStart, PreToolUse)"
echo "   │   ├── rules/"
echo "   │   └── skills/            (add SKILL.md per workflow)"
echo "   ├── .kilocode/             (Kilo Code)"
echo "   │   └── rules/"
echo "   └── .agents/               (Antigravity)"
echo "       └── rules/"
echo ""
echo "📝 Next steps:"
echo "   1. Fill in .memory-bank/ files with project details"
echo "   2. Add skills in .claude/skills/<name>/SKILL.md for project workflows"
echo "   3. Run: cd $PROJECT_PATH && claude"
echo ""
