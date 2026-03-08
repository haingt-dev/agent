#!/bin/bash
# Agent Global Hub - Shell Aliases
# Source this file in your ~/.zshrc or ~/.bashrc:
# source ~/Projects/agent/shell-aliases.sh

# ============================================
# AGENT GLOBAL HUB NAVIGATION
# ============================================

# Quick access to Agent Global Hub
alias ag='cd ~/Projects/agent && ls -la'
alias ag-edit='cd ~/Projects/agent && $EDITOR .'

# Quick access to projects
alias cdp='cd ~/Projects'
alias cdv='cd ~/Projects/Idea_Vault'

# ============================================
# PROJECT MANAGEMENT
# ============================================

# Bootstrap new project
alias bootstrap='~/Projects/agent/bootstrap-project.sh'

# Edit Memory Bank in current project
mbk() {
    if [ -d ".memory-bank" ]; then
        echo "📝 Opening Memory Bank..."
        $EDITOR .memory-bank/
    else
        echo "❌ No Memory Bank found in current directory"
        echo "💡 Run 'bootstrap .' to create one"
    fi
}

# Quick edit task.md
mbt() {
    if [ -f ".memory-bank/task.md" ]; then
        $EDITOR .memory-bank/task.md
    else
        echo "❌ No task.md found. Run 'mbk' to see all Memory Bank files"
    fi
}

# Quick edit context.md (most frequently updated)
mbc() {
    if [ -f ".memory-bank/context.md" ]; then
        $EDITOR .memory-bank/context.md
    else
        echo "❌ No context.md found. Run 'mbk' to see all Memory Bank files"
    fi
}

# View Memory Bank status
mb-status() {
    if [ -d ".memory-bank" ]; then
        echo "📊 Memory Bank Status"
        echo "===================="
        for file in .memory-bank/*.md; do
            if [ -f "$file" ]; then
                filename=$(basename "$file")
                size=$(wc -l < "$file")
                modified=$(stat -c %y "$file" 2>/dev/null || stat -f "%Sm" "$file" 2>/dev/null)
                printf "%-20s | %4d lines | %s\n" "$filename" "$size" "${modified:0:16}"
            fi
        done
    else
        echo "❌ No Memory Bank in current directory"
    fi
}

# ============================================
# AGENT SWITCHING
# ============================================

# Claude CLI shortcut
alias c='claude'

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

        # Show Memory Bank status if exists
        if [ -d ".memory-bank" ]; then
            echo ""
            mb-status
        fi

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
        [ -d "$project/.memory-bank" ] && echo "  ✓ .memory-bank/" || echo "  ✗ .memory-bank/"
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
  cdc <project>   → Switch to project + show Memory Bank

📝 MEMORY BANK
  mbk             → Edit Memory Bank (current project)
  mbc             → Edit context.md (quick access)
  mbt             → Edit task.md (quick access)
  mb-status       → Show Memory Bank file status

🚀 PROJECT MANAGEMENT
  bootstrap <dir> → Bootstrap new project with Memory Bank

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
fi
