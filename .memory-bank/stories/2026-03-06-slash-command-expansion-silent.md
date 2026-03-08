---
title: "Slash Command Expansion trong Claude Code — Silent va Invisible"
date: 2026-03-06
tags: [claude-code, skills, debugging, gotcha]
project: agent
status: draft
---

# Slash Command Expansion trong Claude Code — Silent va Invisible

## TL;DR

Khi `/track` duoc go standalone thi skill expand dung, nhung user khong thay bat ky dau hieu nao. Khi go embedded trong cau thi khong expand luon — va cung khong co dau hieu gi. Hai case trong giong het nhau tu phia user.

## The Problem

Hai go "Ok lam daily quest thoi /track anki start nhe" — mot cau tu nhien kem slash command. Minh thu invoke no qua Skill tool va nhan loi: `Error: Skill track cannot be used with Skill tool due to disable-model-invocation`. Minh workaround bang cach doc thang SKILL.md va thuc hien manual. Task van duoc track, nhung cau hoi dat ra: tai sao error, va tai sao Hai khong thay gi khac biet?

## The Journey

Dieu tra ra 2 behaviors khac nhau cua Claude Code:

**Case 1 — Standalone slash command**: Khi Hai go `/track` rieng mot dong, Claude Code expand no thanh `<command-name>/track</command-name>` + toan bo noi dung SKILL.md trong context cua model. Skill hoat dong dung. Nhung phia Hai: khong co indicator nao — response trong y het Claude tu tra loi.

**Case 2 — Embedded trong text**: Khi Hai go "chay /track start di", Claude Code khong expand. Model nhan plain text. Voi `disable-model-invocation: true`, Skill tool cung bi block -> silent fail hoan toan.

Test duoc verify live trong conversation: go `/track` standalone -> confirm co `<command-name>` tag trong context. Go "chay /track start di" -> confirm khong co tag gi.

Phat hien them: day khong phai bug trong skill design — `disable-model-invocation: true` hoat dong dung nhu documented. Van de la UI cua Claude Code khong expose expansion state cho user.

## The Insight

Claude Code slash commands chi expand khi la **standalone message**, khong phai khi embedded trong text. Day la behavior can biet khi dung skills.

Quan trong hon: ca hai case (expand va khong expand) deu **invisible** voi user — khong co feedback loop nao. Dieu nay khien debugging slash command issues rat kho: user khong biet command co trigger khong, va khi fail thi cung khong biet vi sao.

Ket qua: raise GitHub issue #31344 tai `anthropics/claude-code` de xuat them visual indicator cho slash command expansion.

## Technical Details

- Slash command expansion: `<command-name>skill-name</command-name>` + `<command-message>args</command-message>` tags inject vao model context
- `disable-model-invocation: true` trong frontmatter -> Skill tool bi block, description bi loai khoi context
- Standalone = message chi chua slash command (co the kem args): `/track anki start`
- Embedded = slash command nam trong cau text: "chay /track start di"
- GitHub issue: https://github.com/anthropics/claude-code/issues/31344
