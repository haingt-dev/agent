---
name: reschedule-quest
description: Reschedule recurring quests — shift to next occurrence without completing
---

# Reschedule Quest — Skip Recurring Quests

Reschedule quests you didn't do today. Shifts them to the next occurrence WITHOUT marking as completed — because you didn't do it, so it shouldn't count.

## Usage

```
/reschedule-quest              → show today's skippable tasks, choose what to done/reschedule
/reschedule-quest CCNA         → reschedule specific task by name
```

## How Reschedule Works

**Reschedule ≠ Complete.** Completing a recurring task logs it as done in history and stats. Reschedule uses `mcp__todoist__update-tasks` to shift the due date to the next occurrence — no completion recorded.

For a recurring task with `dueString: "every weekday"`:
- **Complete** → marked done today, next occurrence auto-created (counts in stats)
- **Reschedule** → update dueString to same pattern "every weekday" → Todoist recalculates next due date (nothing in completed history)

<!-- Note: dueString re-submission shifting to next occurrence is undocumented Todoist behavior. Works as of 2026-03. -->

## Todoist Reference

### Mandatory (NEVER reschedule)
- 🔥 Daily Quests (projectId: `6g6f74gGg464CPv9`) — p1 tasks, must be done

### Reschedulable
- ⚔️ Main Quests (projectId: `6g6f74cmqrRj2937`) — p2 tasks
- 🎮 Side Quests (projectId: `6g6f74h9JQXGVX6p`) — p3/p4 tasks

## Flow A: With Argument (`/reschedule-quest CCNA`)

1. Search for the task: `mcp__todoist__find-tasks` with query from argument
2. Verify it's a recurring task (has `recurring` field)
3. Verify it's NOT a Daily Quest (p1 / Daily Quests project)
4. If non-recurring → warn: "Task này không recurring. Muốn reschedule thủ công tới ngày nào?"
5. If Daily Quest → refuse: "Daily Quest không được reschedule. Làm đi!"
6. Reschedule: `mcp__todoist__update-tasks` with the task's existing dueString (preserves recurrence, shifts to next occurrence)
7. Show: "⏭️ Rescheduled: CCNA → next due: [date]"

## Flow B: No Argument (Interactive)

1. Fetch today's tasks: `mcp__todoist__find-tasks-by-date` startDate="today" (includes overdue)
2. Split into groups:

```
### 🔥 Daily Quests (mandatory)
| | Quest | Status |
|---|---|---|
| 🔒 | ELSA Speak | ⬜ pending |
| 🔒 | Mini Output | ⬜ pending |

### Reschedulable Quests
| # | Quest | Project | Due |
|---|---|---|---|
| 1 | CCNA - Học 1h | Main / 🧠 High | today |
| 2 | Rải CV & Research | Main / ⚡ Medium | today |
| 3 | English Shadowing | Main / 🌊 Low | today |
| 4 | Game Dev - Wildtide | Side / 🎯 Passion | today |
| 5 | Đọc sách | Side / 🏠 Life | today |
```

3. Ask Hải: "Tasks nào đã hoàn thành hôm nay?" (expect numbers or names)
4. Process:
   - Tasks Hải says done → `mcp__todoist__complete-tasks` (completed for real)
   - Remaining reschedulable tasks → `mcp__todoist__update-tasks` with existing dueString for each (reschedule)
5. Show summary:

```
### Summary
✅ Done: Rải CV, English Shadowing
⏭️ Rescheduled: CCNA, Game Dev, Đọc sách → next occurrence
🔒 Daily Quests: chưa xong — làm đi!
```

## Rules

- NEVER reschedule Daily Quests (p1 / Daily Quests project) — always refuse
- NEVER use `complete-tasks` for rescheduled tasks — only `update-tasks`
- Only use `complete-tasks` for tasks the user confirms they actually did
- For non-recurring tasks, do NOT auto-reschedule — ask what date to move to
- Keep the interaction fast — one question max, then execute
