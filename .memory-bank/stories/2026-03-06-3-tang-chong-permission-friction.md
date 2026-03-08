---
title: "3 tang chong — permission friction, hook double-gating, va stale worktree"
date: 2026-03-06
tags: [claude-code, permissions, hooks, config-management]
project: agent
status: draft
---

# 3 tang chong — permission friction, hook double-gating, va stale worktree

## TL;DR

Claude Code permission system co 3 van de chong len nhau: MCP tools khong co wildcard, hook duplicate settings tao double-gating, va `.claude/` directory bi gitignore blanket khien config khong portable. Fix bang MCP wildcards o global + trim hook + selective gitignore. Bonus: Claude hoi permission de edit chinh file permission cua no.

## The Problem

Hai bao: "minh van phai approve/deny voi tan suat con nhieu hon truoc". Da setup `Bash(*)` o global, da co hook chan command nguy hiem, nhung friction van tang thay vi giam. Them vao do, `.claude/worktrees/` xuat hien trong git status — mot artifact khong ai nho tao.

## The Journey

**Act 1 — Stale worktree**

Bat dau tu cau hoi "`.claude/worktrees/` la gi?". Hoa ra la git worktree artifact tu session truoc (EnterWorktree tool), branch `worktree-agent-ab515107` dang o commit cu. Don bang `git worktree remove` + xoa branch.

**.gitignore blanket → selective**

De chan `.claude/` khoi git, them `.claude/` vao `.gitignore`. Nhung sau do nhan ra: `settings.json` (enabled plugins, shared config) cung bi ignore — clone repo tren may khac se mat config. Fix: doi sang selective ignore chi cho `settings.local.json`, `worktrees/`, `plans/`.

**Act 2 — Permission audit**

Investigate tai sao van nhieu prompts du da co `Bash(*)`. Phat hien:

1. **MCP tools khong co wildcard**: Global settings co `Bash(*)` nen Bash auto-approve. Nhung MCP tools (todoist, gcal, context7, gmail) phai approve TUNG CAI MOT. Project `settings.local.json` da tich 67 entry — phan lon la MCP tools accumulate qua nhieu session.

2. **Hook duplicate settings**: `pre-tool-safety.sh` check `rm -rf /`, `rm -rf ~`, `git push --force`, `git reset --hard` — nhung global `settings.local.json` DA CO deny/ask rules cho chinh nhung thu do. Hook emit "ask" → settings cung "ask" → double prompt hoac hook block du user da approve trong conversation.

3. **Permissions fragile**: `settings.local.json` (machine-specific) la noi chua permissions. Khi Claude Code update hoac reset, mat het. Permissions durable nen nam trong committed `settings.json`.

**Act 3 — Fix**

- Add 6 MCP wildcards (`mcp__todoist__*`, `mcp__claude_ai_Google_Calendar__*`, etc.) vao global `~/.claude/settings.json` — lazy approach, wildcard khong anh huong neu server khong chay
- Clean global settings: 53 entries → 15 (bo 50+ Bash entries project-specific da duoc cover boi `Bash(*)`)
- Trim hook: bo 4 checks duplicate voi settings, giu 3 checks co gia tri rieng (`rm -rf` general, `git clean -f`, sensitive files)
- Clean project `settings.local.json`: 67 entries → empty

**Bonus — The irony**

Khi Write tool sua `settings.local.json` (chinh file config permission cua Claude Code), Claude... hoi permission. `Edit` tool match theo file path scope, va `.claude/settings.local.json` trigger ask. Tool tu khoa chinh minh.

## The Insight

Permission system cua Claude Code co nhieu layers (settings.json, settings.local.json, hooks) va chung KHONG biet ve nhau. Moi layer duoc design doc lap — settings check rules, hooks check patterns, nhung khong co coordination. Ket qua: friction nhan len thay vi cong lai.

Best practice:
- **Global `settings.local.json`**: safety layer (deny/ask cho catastrophic + dangerous)
- **Global `settings.json`**: convenience layer (MCP wildcards, broad allows)
- **Hooks**: chi check nhung thu settings KHONG cover duoc
- **`.gitignore`**: selective, khong blanket — `settings.json` can committed de portable

## Technical Details

- Permission precedence: deny → ask → allow. First match wins across all layers.
- Hook `PreToolUse` fires BEFORE permission check — co the override allow rules
- MCP wildcard syntax: `mcp__server-name__*` — match all tools from a server
- `Bash(*)` trong allow list covers ALL bash commands
- `settings.local.json` la machine-specific, `settings.json` la shared/committed
- `additionalDirectories` trong settings la project-specific — nen nam trong project config, khong global
