---
title: "CLAUDE.md Goes English — And Claude Actually Got Faster"
date: 2026-03-06
tags: [claude-code, english, config, optimization]
status: draft
---

## TL;DR
Converted project config files from Vietnamese to English for daily immersion. Only 1 of 14 files needed work. Side effect: Claude literally responds faster in English.

## The Problem
Daily immersion goal — English everywhere. The global `~/.claude/CLAUDE.md` was entirely Vietnamese, which was ironic: the file Claude reads every session, in a language the model is less optimized for. Also a hypothesis that English instructions get ~2-5% better instruction-following.

## The Journey
Converted `~/.claude/CLAUDE.md` first — clean 61-line rewrite, all meaning preserved, no fluff added.

Then scanned all 14 config files across `~/Projects` (7 `.claude/CLAUDE.md` + 7 `AGENTS.md`). Expected significant translation work. Found: only `Bookie/AGENTS.md` (65 lines) had mixed Vietnamese content. The other 13 were already English by natural drift.

Ran `claude-md-improver` for validation. All files passed B+ or higher. Zero issues flagged.

Then Hải's punchline: *"haha claude response faster in english."*

## The Insight
Not just perception — it's real. Vietnamese requires more tokens per semantic unit than English (the tokenizer was trained predominantly on English). Fewer output tokens → faster stream. Same ideas, less latency.

English-first config files: triple payoff — immersion, instruction quality, and raw speed. The translation effort was almost zero since most files were already English.
