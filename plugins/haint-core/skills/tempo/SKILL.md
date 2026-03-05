---
name: tempo
description: Daily dashboard — Todoist quests + Google Calendar events + evaluation
---

# Tempo — Daily Dashboard

Fetch and combine data from Todoist and Google Calendar to give Hải a complete daily overview with evaluation. Use timezone Asia/Ho_Chi_Minh.

## Usage

```
/tempo              → today's dashboard
/tempo tomorrow     → tomorrow's dashboard
/tempo weekly       → weekly summary
```

## Step 1: Parse Arguments

- No argument or "today" → target = today
- "tomorrow" / "ngày mai" → target = tomorrow
- "weekly" / "tuần" → switch to Weekly mode (Step 4)
- Specific date → target = that date

## Step 2: Fetch Data (parallel)

Call these 3 in parallel:
1. `mcp__todoist__get-overview` (no params) — project/section structure
2. `mcp__todoist__find-tasks-by-date` with startDate = target date (includes overdue)
3. `mcp__claude_ai_Google_Calendar__gcal_list_events` with timeMin = target 00:00:00, timeMax = target 23:59:59, timeZone = Asia/Ho_Chi_Minh

## Step 3: Present Dashboard

```
## Tempo — [weekday, DD/MM/YYYY]

### Calendar (time anchors)
| Thời gian | Sự kiện |
|---|---|
| HH:MM – HH:MM | event name |

### Quests — Today

**🔗 Anchor Chain (Daily Quests)**
| | Quest | Details |
|---|---|---|
| ✅/⬜ | task name | priority · duration · due time |

**⚔️ Main Quests**
| | Quest | Energy | Labels |
|---|---|---|---|
| ✅/⬜ | task name | 🧠/⚡/🌊 | labels |

**🎮 Side Quests**
| | Quest | Section | Labels |
|---|---|---|---|
| ✅/⬜ | task name | 🎯/🏠 | labels |

### 🏆 Milestones
[milestone tasks with target dates]

### ⚠️ Overdue
| Quest | Due date |
|---|---|
| task name | DD/MM |

### Đánh giá
- Completion: X/Y tasks done
- Overdue: Z tasks
- [Contextual suggestions]
```

## Step 3.1: Evaluation Logic

After rendering the dashboard, add evaluation:

**Completion rate:**
- Count checked vs total tasks for today

**Contextual suggestions:**
- Overdue > 3 → "Nhiều overdue, `/reschedule-quest` để dọn board?"
- All Daily Quests done → positive note
- Inbox has tasks → "Có X tasks chưa phân loại trong Inbox, `/quest` để sort?"
- Heavy day (> 6 tasks) → suggest prioritizing or skipping low-priority items

## Step 4: Weekly Mode

If argument is "weekly" or "tuần":

1. Fetch completed tasks: `mcp__todoist__find-completed-tasks` for last 7 days
2. Fetch current tasks: `mcp__todoist__find-tasks-by-date` startDate="today" daysCount=7
3. Present weekly summary:

```
## Tempo Weekly — [date range]

### Completion Summary
- Total completed: X tasks
- Daily Quests streak: Y/7 days
- Main Quests: X/Y completed
- Side Quests: X/Y completed

### Patterns
[Note any patterns: which days were productive, which quests get skipped often]

### Gợi ý tuần tới
[Actionable suggestions based on patterns]
```

## Rules

- Keep it scannable — no walls of text
- Highlight overdue tasks clearly with ⚠️
- Show ✅ for completed, ⬜ for pending
- This skill is READ-ONLY — do NOT create or modify tasks (use `/quest` for that)
- Do NOT ask follow-up questions after showing dashboard — just present and done
