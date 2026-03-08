---
title: "settings.local.json ton tai, syntax dung, nhung bi ignore hoan toan"
date: 2026-03-06
tags: [claude-code, permissions, config-management, gotcha]
project: agent
status: draft
---

# settings.local.json ton tai, syntax dung, nhung bi ignore hoan toan

## TL;DR

`~/.claude/settings.local.json` khong phai valid settings location o user level — file ton tai, syntax JSON dung, nhung Claude Code silently ignore no. Moi permission rule trong do, bao gom `Bash(*)`, khong co effect.

## The Problem

Can reinstall godot-dev plugin de refresh cache. Don gian: uninstall + install. Nhung thuc thi ton ~14 bash calls va rat nhieu permission prompts, du `~/.claude/settings.local.json` da co `Bash(*)` trong allow list.

## The Journey

**Hypothesis 1: project-level override**
`/agent/.claude/settings.local.json` co `"allow": []` — nghi empty array override global `Bash(*)`. Doc docs -> arrays merge, khong override. Sai.

**Hypothesis 2: plugin commands co permission system rieng**
`claude plugin install` prompt -> nghi Claude Code co mechanism rieng cho plugin commands. Test `echo` -> no prompt, `claude plugin install --help` -> prompt. Ket luan sai — sau do test them thi `ls` va `claude --version` cung deu prompt.

**Hypothesis 3: ExitPlanMode `allowedPrompts` la cause**
Nghi allowedPrompts restrict commands sau plan mode. Sai — `ls` va `claude --version` prompt ngay ca ngoai plan mode.

**Breakthrough:**
Pattern ro: `echo` -> no prompt, moi thu khac -> prompt. Day la pattern cua "khong co rule nao ca". Tra lai docs settings hierarchy:

```
1. Managed settings
2. CLI arguments
3. .claude/settings.local.json (PROJECT local)
4. .claude/settings.json (project shared)
5. ~/.claude/settings.json (USER global)
```

Khong co `~/.claude/settings.local.json`. File nay khong ton tai trong hierarchy -> **bi ignore hoan toan**.

Fix: merge deny/ask/allow tu `~/.claude/settings.local.json` vao `~/.claude/settings.json`. Ket qua: `ls`, `claude plugin install --help` -> no prompt.

## The Insight

**`settings.local.json` chi valid o project level** (`.claude/settings.local.json`), khong phai user level. O user level, chi co `~/.claude/settings.json`.

Silent failure la phan nguy hiem nhat: file ton tai, syntax dung, khong co error — Claude Code chi don gian khong load no. Minh da configure permissions o sai cho ma khong biet bao lau.

## Technical Details

Settings hierarchy cua Claude Code (user level -> project level):
- `~/.claude/settings.json` — user global
- `.claude/settings.json` — project shared
- `.claude/settings.local.json` — project local, gitignored
- `~/.claude/settings.local.json` — **NOT in hierarchy**, silently ignored

Arrays merge (concatenate + deduplicate). Deny o bat ky level nao wins.
