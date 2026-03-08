---
title: "rm -rf và skill vừa tạo xong — bài học về kiểm tra untracked files"
date: 2026-03-08
tags: [debugging, claude-code, skills, gotcha]
project: "agent"
status: draft
---

# rm -rf và skill vừa tạo xong — bài học về kiểm tra untracked files

## TL;DR

Trong quá trình restructure haint-core plugin từ skills+hooks thành hooks-only, `rm -rf plugins/haint-core/skills/` đã xóa luôn `token-optimize/` — một skill hoàn chỉnh 240 dòng chưa bao giờ được commit. Phục hồi từ session log.

## The Problem

Cần move quest và tempo skills ra khỏi plugin vào project-level. Plugin giờ chỉ cần hooks. Xóa thư mục `skills/` trong plugin source là bước hợp lý.

## The Journey

`git status` trước đó cho thấy `?? plugins/haint-core/skills/token-optimize/` — rõ ràng là untracked. Nhưng không kiểm tra kỹ trước khi `rm -rf`. Kết quả: file chưa staged, chưa committed, gone. Git không recover được.

Phải tìm trong session log của Bookie project (`b7864557.jsonl`) tại `~/.claude/projects/<project-hash>/` — replay 1 Write + 8 Edit operations để reconstruct nguyên bản. Mất ~10 phút + 50 tool calls của subagent.

## The Insight

Trước khi `rm -rf` bất kỳ directory nào, check cụ thể:

```bash
git status --short <dir>
```

Để thấy untracked files bên trong. Untracked = không có trong git history = không recover được nếu xóa.

Rule mới: nếu thấy `??` trong `git status` mà liên quan đến directory sắp xóa → stage hoặc note trước, rồi mới xóa.

## Technical Details

Claude Code giữ toàn bộ session log dạng JSONL tại `~/.claude/projects/<project-hash>/`. Mỗi tool call (Write, Edit, Bash...) được record đầy đủ với params và kết quả. Đây là "backup ngẫu nhiên" — không phải giải pháp, nhưng cứu được trong tình huống này.

Session log tồn tại miễn là conversation chưa bị xóa khỏi Claude Code history.
