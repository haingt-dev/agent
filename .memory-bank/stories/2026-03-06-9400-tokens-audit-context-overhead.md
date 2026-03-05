---
title: "9,400 tokens trước khi gõ chữ nào — audit context overhead của Claude Code plugins"
date: 2026-03-06
tags: [token-optimization, plugin-system, claude-code, architecture]
project: "agent"
status: draft
---

# 9,400 tokens trước khi gõ chữ nào — audit context overhead của Claude Code plugins

## TL;DR
Mỗi conversation Claude Code tốn ~9,400 tokens overhead chỉ cho system prompt, skill descriptions, MCP instructions — trước khi user gõ chữ nào. Sau khi audit và optimize (trim descriptions, uninstall unused plugins, bỏ auto-story từ ship), giảm ~5,000-7,000 tokens/conversation.

## The Problem
Từ khi cho Claude tự gọi tất cả skills, cảm giác tốn token hơn hẳn. Nhưng "cảm giác" thì không actionable — cần số liệu cụ thể.

## The Journey
Bắt đầu bằng câu hỏi đơn giản: "Skills chiếm bao nhiêu context?"

Audit toàn bộ ~/Projects phát hiện **64 SKILL.md files** across 10 projects, 2 marketplace plugins. Nhưng token overhead không đến từ chỗ tưởng:

**Plot twist #1: Kẻ thù lớn nhất không phải skills của mình.**
- `plugin-dev` (official Anthropic plugin) chiếm **~1,760 tokens/conversation** — 8 skills + 3 agents — load MỌI conversation dù chỉ cần khi dev plugin
- Todoist MCP instructions: **~1,800 tokens** best practices documentation, không giảm được

**Plot twist #2: Hai loại tốn token khác nhau.**
- **Description overhead** (~2,500 tokens) — skill descriptions luôn trong system prompt, dù không ai gọi
- **Invocation overhead** (~1,000-1,200 tokens/lần) — khi Claude tự quyết gọi skill, load toàn bộ SKILL.md + execute

Loại 2 mới là cái "cảm thấy tốn". Claude auto-invoke 3 skills không cần thiết = 3,000+ tokens bay.

**Plot twist #3: `disable-model-invocation` không phải giải pháp.**
Field này block luôn cả `/ship` slash command vì slash commands cũng đi qua Skill tool. Giải pháp thực sự: **trim description** — bỏ "Use when user says..." patterns. Claude không biết khi nào trigger → không auto-invoke. Nhưng `/ship` vẫn chạy vì slash command infrastructure pass trực tiếp, không cần match description.

## The Insight
Context overhead là death by a thousand cuts. Không có 1 thứ nào chiếm quá nhiều, nhưng 26 skill descriptions + 8 agent descriptions + MCP instructions cộng lại thành 9,400 tokens mỗi conversation. Optimization quan trọng nhất không phải giảm từng byte — mà là **ngăn auto-invocation** (description trimming) và **uninstall plugins không dùng thường xuyên** (reinstall khi cần chỉ mất 1 command).

## Technical Details
Breakdown cụ thể trước optimization:

| Source | ~Tokens |
|---|---|
| Base system prompt (Claude Code) | 3,000 |
| Todoist MCP instructions | 1,800 |
| plugin-dev (8 skills + 3 agents) | 1,760 |
| haint-core (10 skill descriptions) | 700 |
| CLAUDE.md + MEMORY.md | 1,200 |
| Còn lại (Context7, built-in skills, tools list, git status) | 940 |
| **Tổng** | **9,400** |

Actions taken → v2.1.0:
- Uninstall plugin-dev, skill-creator, claude-md-management (−2,260 tokens)
- Trim descriptions 8/10 skills — bỏ trigger lists (−400 tokens, +ngăn auto-invoke)
- Ship: bỏ Step 3.5 Auto-capture Story — 50 dòng (−500 tokens/invoke)
- Quest: model sonnet thay opus, Story: model sonnet + allowed-tools
