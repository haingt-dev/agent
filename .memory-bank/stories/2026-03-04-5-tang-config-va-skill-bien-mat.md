---
title: "5 tầng config và skill biến mất không dấu vết"
date: 2026-03-04
tags: [debugging, plugin-system, claude-code, config-management]
project: "agent"
status: draft
---

# 5 tầng config và skill biến mất không dấu vết

## TL;DR
Một skill plugin không load được vì 5 tầng config của Claude Code plugin system
phải đồng bộ hoàn hảo — miss một version number ở tầng giữa là skill biến mất
mà không có error nào báo.

## The Problem
Skill `/story` vừa thêm vào plugin `haint-core` nhưng không xuất hiện trong
Claude Code. Không error, không warning — đơn giản là nó không tồn tại.

## The Journey
**Lần 1 — tưởng cache stale:** So sánh source vs cache, thấy cache thiếu
`story/SKILL.md`. Commit file, bump version 1.2.0 → 1.3.0, chạy
`claude plugin update`. Cache refresh thành công, file đã có trong cache.
Restart session — vẫn không thấy skill. Thất vọng.

**Lần 2 — audit sâu hơn:** Deploy 3 explore agents song song quét toàn bộ
hệ thống. Phát hiện `marketplace.json` (index chính của marketplace) vẫn
khai báo version `1.2.0` trong khi `plugin.json` đã là `1.3.0`. Đây là tầng
config bị miss — marketplace index nói "1.2.0 là latest" nên Claude Code
không nhận ra 1.3.0 mới.

**Bonus — 9 vấn đề khác lòi ra:** Khi đã mở nắp kiểm tra, phát hiện thêm:
duplicate Notification hook (nhận 2 notification mỗi lần), Bookie MCP dùng
CLI flag không tồn tại (`-c`), ~30 dòng stale permissions rác,
`bootstrap-project.sh` sai marketplace name, godot-debugging có invalid
frontmatter, blocklist có test entries, stale path references trong MEMORY.md.

**Fix:** 10 changes, 1 commit gộp. Restart session — `haint-core:story`
xuất hiện ngay trong available skills.

## The Insight
Plugin system của Claude Code có 5 tầng config phải khớp nhau:

```
source plugin.json → marketplace.json → cache → installed_plugins.json → runtime
```

Mỗi tầng có version/path/SHA riêng. Miss sync ở bất kỳ tầng nào thì skill
biến mất — **silent failure, không error**. Đây là loại bug khó nhất: mọi thứ
trông đúng nhưng không hoạt động.

Bài học: Khi build plugin system có nhiều tầng cache, cần validation tool
kiểm tra tính nhất quán giữa các tầng. Hoặc ít nhất là log warning khi
phát hiện version mismatch.

## Technical Details
**5 tầng config:**
1. `plugins/haint-core/.claude-plugin/plugin.json` — source of truth
2. `.claude-plugin/marketplace.json` — marketplace index, khai báo plugins
   available
3. `~/.claude/plugins/cache/haint-marketplace/haint-core/<version>/` — cached
   copy
4. `~/.claude/plugins/installed_plugins.json` — tracking installed version +
   gitCommitSha
5. Runtime skill discovery — scan `skills/` directory trong cache path

**Root cause cụ thể:** Khi bump `plugin.json` từ 1.2.0 → 1.3.0, quên update
`marketplace.json` cùng lúc. `claude plugin update` chạy thành công (copy
files vào cache 1.3.0) nhưng marketplace index vẫn nói "latest = 1.2.0",
gây confusion cho runtime loader.
