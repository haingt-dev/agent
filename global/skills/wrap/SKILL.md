---
name: wrap
description: "Quick session save before compact — scan conversation, extract decisions/discoveries/patterns, save to brain. Use when Hải says 'wrap', 'save session', or is about to compact/clear."
argument-hint: ""
allowed-tools: mcp__haingt-brain__brain_session, mcp__haingt-brain__brain_save
---

# Wrap — Session Save

Fast, non-interactive session save. Scan conversation → extract learnings → save to brain → report. No questions, no confirmation.

Use before `/compact` or `/clear` to capture what the PreCompact hook's regex can't: nuanced decisions, context behind choices, and cross-cutting patterns.

## Steps

### 1. Scan Conversation

Review the full conversation and extract:

- **Decisions** (1-3): architectural choices, trade-offs, approaches chosen with reasoning. Format: "[what was decided] — [why]"
- **Discoveries** (1-3): bugs found, root causes, things that worked/didn't, surprising findings. Format: "[what was found] — [evidence/context]"
- **Patterns** (0-1): reusable approaches worth remembering across sessions. Only if genuinely new.

Quality bar: only extract what would be useful 30+ days from now. Skip ephemeral details, debugging steps, and anything obvious from code/git history.

### 2. Dedup

Check the conversation for existing `brain_save` calls. If a learning was already saved during the session (same topic, same conclusion), skip it. Don't duplicate.

### 3. Save

Detect project from cwd (the project name under `~/Projects/`).

Call `brain_session("save")` with:
```
brain_session(
  action: "save",
  summary: "Session [date]: [1-line summary of main work done]",
  decisions: [...extracted decisions...],
  discoveries: [...extracted discoveries...]
)
```

For patterns (if any), use `brain_save` separately since `brain_session` doesn't have a patterns field:
```
brain_save(content: "...", type: "pattern", tags: [...], project: "...")
```

### 4. Report

Print a concise summary:
```
Wrapped: [N] decisions, [N] discoveries, [N] patterns saved.
Ready to /compact.
```
