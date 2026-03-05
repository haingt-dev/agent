---
title: "3 lan sai root cause — hanh trinh debug Claude Code plugin cache"
date: 2026-03-05
tags: [debugging, claude-code, plugin-system, expectation-flip]
status: draft
---

## TL;DR

Xoa `disable-model-invocation` khoi skill files, tuong xong — nhung phai sai 3 lan moi tim dung cho Claude Code thuc su doc metadata: khong phai file tren disk, khong phai git HEAD, ma la plugin cache snapshot tu luc install.

## The Problem

Muon bo `disable-model-invocation: true` de `/ship` va cac skills khac co the invoke qua Skill tool. Tuong xoa flag la xong.

## The Journey

1. **Lan 1 — xoa flag trong source files**: Grep confirm zero matches. Session moi van block. Gia thuyet: "Claude Code doc tu git HEAD, khong phai working directory."

2. **Lan 2 — commit roi thi duoc**: Commit changes. `git show HEAD` confirm flag da mat. Session moi... van block. Gia thuyet sai.

3. **Lan 3 — tim plugin cache**: Do `~/.claude/plugins/cache/haint-marketplace/haint-core/1.5.0/` — flag van con nguyen. `installed_plugins.json` tro vao cache, khong phai source. `claude plugin update` cung khong refresh files. Phai `uninstall` + `install` lai.

## The Insight

Claude Code plugin system co 3 layers khong ai noi cho minh biet:

- **Source files** (project repo) — noi minh edit
- **Git HEAD** — noi minh tuong Claude Code doc
- **Plugin cache** (`~/.claude/plugins/cache/`) — noi Claude Code thuc su doc

Moi lan "fix" chi update 1 layer, 2 layers kia van stale. Va `plugin update` chi update version reference trong `installed_plugins.json`, khong re-copy files. Phai uninstall + install moi refresh cache.

Bonus: `disable-model-invocation` ten goi goi y "ngan model tu y invoke" nhung thuc te la hard block hoan toan — ke ca user chu dong yeu cau, Skill tool van reject.

## Technical Details

- Cache path: `~/.claude/plugins/cache/{marketplace}/{plugin}/{version}/`
- `installed_plugins.json`: tracks installPath, version, gitCommitSha
- `claude plugin update` — updates version + metadata, does NOT re-copy skill files
- `claude plugin uninstall` + `install` — full re-cache from source
