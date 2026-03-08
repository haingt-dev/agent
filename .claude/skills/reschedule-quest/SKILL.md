---
name: reschedule-quest
description: "Reschedule recurring quests — shift to next occurrence without completing. Not the same as marking done."
argument-hint: "[task-name]"
model: sonnet
disable-model-invocation: true
allowed-tools: mcp__todoist__find-tasks, mcp__todoist__find-tasks-by-date, mcp__todoist__update-tasks, mcp__todoist__complete-tasks
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

**Important:** The dueString re-submission technique (setting the same dueString to shift to next occurrence) is undocumented Todoist behavior. It works as of 2026-03 but could change without notice. After each reschedule, verify the due date actually changed by checking the task's updated due info. If the date didn't change (Todoist stopped supporting this), fall back to manually computing the next date and setting `dueDate` directly.

## Todoist Reference

### Mandatory (NEVER reschedule)
- Daily Quests (projectId: `6g6f74gGg464CPv9`) — p1 tasks, must be done

### Reschedulable
- Main Quests (projectId: `6g6f74cmqrRj2937`) — p2 tasks
- Side Quests (projectId: `6g6f74h9JQXGVX6p`) — p3/p4 tasks

## Flow A: With Argument (`/reschedule-quest CCNA`)

1. Search for the task: `mcp__todoist__find-tasks` with query from argument
2. Verify it's a recurring task (has `recurring` field)
3. Verify it's NOT a Daily Quest (p1 / Daily Quests project)
4. If non-recurring → warn: "Task nay khong recurring. Muon reschedule thu cong toi ngay nao?"
5. If Daily Quest → refuse: "Daily Quest khong duoc reschedule. Lam di!"
6. Reschedule: `mcp__todoist__update-tasks` with the task's existing dueString (preserves recurrence, shifts to next occurrence)
7. Verify: fetch the task again to confirm due date changed. If it didn't change, warn and retry with explicit next date via `dueDate`
8. Show: "Rescheduled: CCNA → next due: [date]"

## Flow B: No Argument (Interactive)

1. Fetch today's tasks: `mcp__todoist__find-tasks-by-date` startDate="today" (includes overdue)
2. Split into groups:

```
### Daily Quests (mandatory)
| | Quest | Status |
|---|---|---|
| lock | ELSA Speak | pending |
| lock | Mini Output | pending |

### Reschedulable Quests
| # | Quest | Project | Due |
|---|---|---|---|
| 1 | CCNA - Hoc 1h | Main / High | today |
| 2 | Rai CV & Research | Main / Medium | today |
| 3 | English Shadowing | Main / Low | today |
| 4 | Game Dev - Wildtide | Side / Passion | today |
| 5 | Doc sach | Side / Life | today |
```

3. Ask Hai: "Tasks nao da hoan thanh hom nay?" (expect numbers or names)
4. Process:
   - Tasks Hai says done → `mcp__todoist__complete-tasks` (completed for real)
   - Remaining reschedulable tasks → `mcp__todoist__update-tasks` with existing dueString for each (reschedule)
5. Show summary:

```
### Summary
Done: Rai CV, English Shadowing
Rescheduled: CCNA, Game Dev, Doc sach → next occurrence
Daily Quests: chua xong — lam di!
```

## Rules

- NEVER reschedule Daily Quests (p1 / Daily Quests project) — always refuse
- NEVER use `complete-tasks` for rescheduled tasks — only `update-tasks`
- Only use `complete-tasks` for tasks the user confirms they actually did
- For non-recurring tasks, do NOT auto-reschedule — ask what date to move to
- Keep the interaction fast — one question max, then execute
