#!/usr/bin/env bash
# Claude Code status line for Hải
# Catppuccin Mocha palette — works well in dimmed terminal colors

input=$(cat)

cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // ""')
model=$(echo "$input" | jq -r '.model.display_name // ""')
used=$(echo "$input" | jq -r '.context_window.used_percentage // empty')

# Shorten home prefix
cwd="${cwd/#$HOME/~}"

# Git branch (skip optional locks, ignore errors)
branch=$(git -C "${cwd/#\~/$HOME}" --no-optional-locks branch --show-current 2>/dev/null)

# Build context segment
ctx_seg=""
if [ -n "$used" ]; then
  used_int=${used%.*}
  if [ "$used_int" -ge 80 ]; then
    # high usage — red-ish
    ctx_seg=$(printf " \033[0;31mctx:%s%%\033[0m" "$used_int")
  elif [ "$used_int" -ge 50 ]; then
    # mid usage — yellow-ish
    ctx_seg=$(printf " \033[0;33mctx:%s%%\033[0m" "$used_int")
  else
    ctx_seg=$(printf " ctx:%s%%" "$used_int")
  fi
fi

# Build branch segment
branch_seg=""
if [ -n "$branch" ]; then
  branch_seg=$(printf " \033[0;34m(%s)\033[0m" "$branch")
fi

printf "\033[0;35m%s\033[0m%s \033[0;36m%s\033[0m%s" \
  "$cwd" \
  "$branch_seg" \
  "$model" \
  "$ctx_seg"
