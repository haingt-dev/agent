# Output Formats Reference

Read at the final step of any mode, before rendering output.

## Proposal Format (Modes 1 & 2)

Present the full day schedule with these sections:

```
📅 [Day] [DD/MM] — [Context summary]
Wake: HH:MM (±delta vs normal) | NOW: HH:MM | Bed: HH:MM | IF: fasting until dinner ~17:00
⚠️ [Any warnings: early wake, sleep debt, cortisol load, etc.]

[Đã qua]
✅ HH:MM  [emoji] Activity description (completed/past)
✅ HH:MM  [emoji] Activity description (completed/past)

[Hiện tại → HH:MM]
▶️ HH:MM  [emoji] Currently active activity (ends HH:MM)

[Còn lại]
⏰ HH:MM  [emoji] Activity description
⏰ HH:MM  [emoji] Activity description
...

📆 Calendar changes:
  ➕ ADD: "Event name" HH:MM-HH:MM
  ✏️ MOVE: "Event name" HH:MM → HH:MM (reason)
  ❌ DELETE: "Event name" (reason)
  ⚠️ CONFLICT: "Event name" — needs decision

📋 Todoist changes:
  ⏰ TIME: "Task name" → dueString "today at HH:MM" (materialized to calendar via sync)
  ➡️ RESCHEDULE: "Task name" DD/MM → DD/MM (reason)
  ⚠️ DEADLINE: "Task name" — deadline DD/MM approaching, prioritized to [slot]
  ➕ ADD: "Task name" DD/MM, Section / Energy (reason)
  💡 TIP: suggestion

⚠️ Cần Hải quyết:
  → [Decision items that need human input]

Science notes:
  [Brief explanation of key scheduling decisions — WHY each choice]
```

## Activity Emojis

🌅 Wake · 🚗 Travel/đưa đón · 🧘 Movement · 🔗 Anchor Chain · ☕ Cold brew · 🧠 Deep work · ⚡ Medium · 🌊 Low/reading · ☀️ Break · 😴 Sleep/nap · 🏃 Exercise · 🍽️ Dinner · 🚶 Walk · 🎮 Creative · 📖 Reading · 📵 Screens off · 🏠 Life admin · 💒 Social · 👔 Prep

## Cleanup Summary Format (Mode 3)

```
### Summary
✅ Done: [completed tasks]
➡️ Rescheduled: [tasks] → next occurrence
🔗 Daily Quests: chưa xong — làm đi!
🧹 Calendar: deleted [N] stale [alfred] blocks
```

## Task Result Table (Mode 4)

```
### Tasks Created
| Task | Project / Section | Priority | Labels | Duration | Deadline | Phase | Materialized |
|------|-------------------|----------|--------|----------|----------|-------|-------------|
| build portfolio site | Main / 💰 Income | p2 | high_energy | 90m | — | prove | ⏰ PEAK (open-ended) |
| run IPA pipeline | Main / 🧠 Growth | p2 | medium_energy | 45m | — | execute | ⏰ 14:00-14:45 |
| mua sữa cho vợ | Side / 🏠 Life | p3 | low_energy | 30m | — | execute | — |
| Apr 30 check | Main / 🏆 Milestones | p2 | high_energy | 45m | ⚠️ 04/30 | execute | ⏰ 09:00-09:45 |
```

## Weekly Review Format (Mode 5)

### Proposal Preview
```
📅 Weekly Review — {WEEK_LABEL} ({WEEK_START} → {WEEK_END})

### ✅ Completed ({count})

**⚔️ Main Quests**
- [x] Task name (💰 Income) — {completion_date}
- [x] Task name (🧠 Growth) — {completion_date}

**🎮 Side Quests**
- [x] Task name (🏠 Life) — {completion_date}

### ➡️ Carried Over ({count})
- [ ] Task name (💰 Income) — due {date}
- [ ] Task name (🧠 Growth) — due {date}
```

### Note Review Section (written to file via obsidian patch)
```
## 📊 Review

### ✅ Completed ({X})
- [x] Task name (💰 Income) — {date}
- [x] Task name (🧠 Growth) — {date}

### ➡️ Carried Over ({Y})
- [ ] Task name (💰 Income) — due {date}
- [ ] Task name (🧠 Growth) — due {date}
```

### Summary
```
✅ Completed: {X} tasks
➡️ Carried over: {Y} tasks
📝 Note updated: {NOTE_PATH}
```
