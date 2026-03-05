---
title: "Claude Code doc skill metadata tu git HEAD, khong phai working directory"
date: 2026-03-05
tags: [claude-code, plugin-system, gotcha, tooling]
status: draft
---

## TL;DR

`disable-model-invocation: true` trong skill frontmatter block Skill tool hoan toan -- ke ca khi user yeu cau. Va Claude Code doc skill metadata tu git HEAD, khong phai file tren disk. Xoa flag trong file nhung chua commit = van bi block.

## The Problem

Dang build plugin system cho Claude Code: ship, tempo, quest, story... Muon ngan Claude tu y invoke cac skill nhu `/ship` (auto-commit nguy hiem), nen dat `disable-model-invocation: true` trong frontmatter.

## The Journey

1. **Flag qua manh**: `disable-model-invocation` khong chi ngan auto-invocation -- no block ca Skill tool. User noi "ship thu" va Claude goi Skill tool → bi reject. Khong phai "ngan Claude tu y goi" ma la "cam goi hoan toan qua code".

2. **Xoa flag, van bi block**: Xoa `disable-model-invocation` khoi tat ca SKILL.md files. Grep confirm: zero matches. Nhung session moi van bao "cannot be used with Skill tool due to disable-model-invocation".

3. **Root cause**: `git show HEAD:plugins/haint-core/skills/ship/SKILL.md` van co flag. Claude Code doc skill metadata tu **committed version** (git HEAD), khong phai working directory. File tren disk da thay doi nhung chua commit = Claude Code van thay phien ban cu.

## The Insight

Claude Code plugin system co 2 gotcha chua document:

1. **`disable-model-invocation` la hard block**, khong phai soft hint. No ngan moi cach invoke qua Skill tool, ke ca khi user chu dong yeu cau.

2. **Skill metadata doc tu git HEAD**. Day la design choice (co le de tranh load file chua stable), nhung consequence la: moi thay doi vao skill frontmatter phai commit truoc thi session moi moi pick up.

Implication: Neu dang dev plugin, phai commit skill files truoc khi test. Khong the edit-and-reload nhu config file binh thuong.

## Technical Details

- Claude Code version: CLI (2026-03)
- Plugin location: `~/Projects/agent/plugins/haint-core/`
- Frontmatter flag: `disable-model-invocation: true` trong YAML frontmatter cua SKILL.md
- Verification: `git show HEAD:<path>` vs `cat <path>` cho thay 2 versions khac nhau
