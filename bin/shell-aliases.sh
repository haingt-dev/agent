#!/bin/bash
# Agent Global Hub - Shell Aliases
# Source this file in your ~/.zshrc or ~/.bashrc:
# source ~/Projects/agent/bin/shell-aliases.sh

# Load local env (not committed) — lives at repo root, one level above bin/
_AGENT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
[ -f "$_AGENT_ROOT/.env" ] && source "$_AGENT_ROOT/.env"

# ============================================
# AGENT GLOBAL HUB NAVIGATION
# ============================================

# Quick access to Agent Global Hub
alias ag='cd ~/Projects/agent && ls -la'
alias ag-edit='cd ~/Projects/agent && $EDITOR .'

# Quick access to projects
alias cdp='cd ~/Projects'
alias cdv='cd ~/Projects/Idea_Vault'

# Digital Identity — life management hub
alias di='cd ~/Projects/digital-identity'
alias dic='cd ~/Projects/digital-identity && claude --continue'

# ============================================
# PROJECT MANAGEMENT
# ============================================

# Bootstrap new project
alias bootstrap='~/Projects/agent/bin/bootstrap-project.sh'

# ============================================
# AGENT SWITCHING
# ============================================

# Claude CLI shortcuts
alias c='claude --permission-mode auto'  # auto mode: classifier-gated (safe actions run, risky ones prompt)

# Show agent priority
alias ag-priority='echo "🎯 Agent: Claude Code (c)"'

# Quick project switch with Claude
cdc() {
    if [ -z "$1" ]; then
        echo "Usage: cdc <project-name>"
        echo "Available projects:"
        ls -1 ~/Projects/
        return 1
    fi

    PROJECT_PATH="$HOME/Projects/$1"
    if [ -d "$PROJECT_PATH" ]; then
        cd "$PROJECT_PATH"
        echo "📂 Switched to: $PROJECT_PATH"

        # Offer to start Claude
        echo ""
        echo "💡 Start Claude? (c)"
    else
        echo "❌ Project not found: $PROJECT_PATH"
    fi
}

# ============================================
# MAINTENANCE
# ============================================

# Check agent setup across all projects
ag-status() {
    echo "🔄 Checking agent setup in all projects..."
    for project in ~/Projects/*/; do
        name=$(basename "$project")
        echo ""
        echo "--- $name ---"
        [ -f "$project/AGENTS.md" ] && echo "  ✓ AGENTS.md" || echo "  ✗ AGENTS.md"
        [ -f "$project/.claude/CLAUDE.md" ] && echo "  ✓ .claude/" || echo "  ✗ .claude/"
    done
}

# ============================================
# HELP
# ============================================

# Show this help
ag-help() {
    cat << 'EOF'
╔═══════════════════════════════════════════════════════════╗
║         AGENT GLOBAL HUB - COMMAND REFERENCE              ║
╚═══════════════════════════════════════════════════════════╝

📁 NAVIGATION
  ag              → Go to Agent Global Hub
  ag-edit         → Open Agent Global Hub in editor
  cdp             → Go to ~/Projects
  cdv             → Go to Obsidian Vault
  di              → Go to Digital Identity
  dic             → Go to Digital Identity + resume Claude session
  cdc <project>   → Switch to project

🚀 PROJECT MANAGEMENT
  bootstrap <dir> → Bootstrap new project

🤖 AGENTS
  c               → Start Claude
  ag-priority     → Show agent priority chain

🔧 MAINTENANCE
  ag-status       → Check agent setup across all projects

📚 HELP
  ag-help         → Show this help

EOF
}

# Auto-completion for cdc (project names)
if [ -n "$ZSH_VERSION" ]; then
    # Zsh completion
    compdef '_files -W ~/Projects -/' cdc
elif [ -n "$BASH_VERSION" ]; then
    # Bash completion
    _cdc_completion() {
        local cur="${COMP_WORDS[COMP_CWORD]}"
        COMPREPLY=( $(compgen -W "$(ls -1 ~/Projects/)" -- "$cur") )
    }
    complete -F _cdc_completion cdc
fi

# Show welcome message on first source
if [ -z "$AG_ALIASES_LOADED" ]; then
    export AG_ALIASES_LOADED=1
    echo "✅ Agent Global Hub aliases loaded! Type 'ag-help' for commands."
    echo "📱 Remote: ssh haint@${AG_REMOTE_IP:-<set AG_REMOTE_IP>} | tmux new -s work | tmux attach -t work"
fi
