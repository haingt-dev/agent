---
name: godot-check-gdd
description: "Check recent Godot code changes against the project's GDD + design pillars for alignment."
model: sonnet
allowed-tools: Read, Grep, Glob, Bash(git *), mcp__claude_ai_Context7__query-docs
argument-hint: "[commit count or range]"
---

# Godot — Check GDD alignment

Review what the code is actually doing against what the GDD says it should — so implementation
drift and scope creep get caught early, while they're cheap to fix. This skill is generic: it reads
the project's own pillars and sections (never hardcoded), so it works on any Godot project that
follows the `docs/gdd/` convention.

## Why this matters

A solo dev moves fast and the code quietly diverges from the design — or worse, grows features the
pillars never asked for. The GDD's **stable Core (pillars)** is the yardstick: every change should
serve a pillar, and anything that fights one is either a design decision to record or a mistake to
revert. Catching that in a 10-commit window is a conversation; catching it after a month is a rewrite.

## Procedure

1. **Load the design** (the yardstick — read, don't assume):
   - `docs/gdd/{PREFIX} - Design Pillars.md` — the pillars (the primary test).
   - `docs/gdd/GDD - {codename}.md` — the index, to see which sections are `complete` vs `stub`.
   - The specific section note(s) relevant to the changed code.
   If `docs/gdd/` is absent, say so and fall back to `docs/STATUS.md` / `CLAUDE.md` pillars — don't invent pillars.

2. **Identify the changes:**
   ```
   git log --oneline -10
   git diff HEAD~<N> --stat
   ```
   Use `$ARGUMENTS` (a commit count or range) if given. Read the changed files to understand what
   actually shipped.

3. **Analyze alignment** against each pillar and the relevant section's spec. For uncertain Godot-4
   API questions, confirm via Context7 rather than guessing.

4. **Report** in these buckets:
   - **✅ Aligned** — changes that serve a pillar / match the section spec.
   - **⚠️ Divergent** — code that contradicts a pillar or a `complete` section (cite the pillar/section).
   - **🔺 Scope risk** — new surface area no pillar asked for (the solo-dev trap; flag it for a cut/defer decision).
   - **→ Recommendations** — update the GDD to match reality, revert the code, or simplify.

Be specific and cite the exact pillar/section. The goal is a fast, honest alignment read — not a lint.
