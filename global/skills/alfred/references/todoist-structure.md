# Todoist Structure — Full Reference

Read when creating/updating tasks and need label semantics or section IDs beyond the quick lookup in SKILL.md.

## Labels

### Energy labels (for scheduling — alfred maps these to circadian windows):

| Label | Alfred mapping | When to schedule |
|-------|---------------|-----------------|
| `high_energy` | PEAK windows (W+1.5h to W+5h) | Deep focus, building, complex problem-solving |
| `medium_energy` | TRANSITION + PRE-DINNER | Reviews, coordination, moderate cognitive load |
| `low_energy` | MID-DAY dip, post-dinner | Reading, passive learning, light research |

### Topic labels (for cross-cutting queries):

| Label | When to apply |
|-------|---------------|
| `english` | English/language learning |
| `creative` | Design, writing, video, art, building |
| `life` | Personal life management |
| `chain_english` | Anchor Chain habit only (Anki/ELSA) |

## Priority Convention

p1 = reserved (formerly Anchor Chain — now calendar-only). p2 = Main Quests (career/life impact). p3 = Side Quests (optional). p4 = Rewards/backlog. Pass as `priority: "p2"` etc.

## Daily Habits — Calendar-Only

Moved to Google Calendar as recurring events (no longer in Todoist):
- 🏃 Exercise 06:30-07:00, 🃏 Anki 07:00-07:20, 🗣️ ELSA 07:20-07:40, ✍️ Mini Output 07:40-07:55
- All marked `[alfred]` in description. No tick-done — calendar presence = commitment.

---

## Pro Features

### reschedule-tasks vs update-tasks

| Situation | Tool | Why |
|-----------|------|-----|
| Move task to different date | `reschedule-tasks` | Preserves recurrence |
| Add time to today (non-recurring) | `update-tasks` + dueString | Safe — no recurrence |
| Add time to today (recurring) | `reschedule-tasks` + datetime | Preserves recurrence |
| Change metadata (labels, priority, etc.) | `update-tasks` | No date change — always safe |

**Detection:** Check `recurring` field on fetched task. Truthy → `reschedule-tasks` for any date change.

### deadlineDate

- ISO 8601: `"YYYY-MM-DD"` (e.g., `"2026-04-30"`)
- Set via `add-tasks` or `update-tasks` — immovable hard deadline
- Remove: `update-tasks` with `deadlineDate: "remove"`
- Alfred: deadlines within 48h → one priority tier higher

### duration

- Format: `"90m"`, `"2h"`, `"2h30m"`
- Set via `add-tasks` or `update-tasks`
- Visible in calendar view
- Alfred Mode 2 reads this for slot allocation. Missing → estimate from energy label

### Reminders

Three types: `relative` (minuteOffset before due), `absolute` (specific datetime), `location` (geofence).

| Scenario | Type | Config |
|----------|------|--------|
| Standard timed task | relative | minuteOffset: 10, push |
| Deadline < 48h | relative | Add second at minuteOffset: 60 |
| Prove-phase PEAK | relative | minuteOffset: 0 (instant) |

Tools: `add-reminders` (max 25/call), `find-reminders` (by taskId), `update-reminders`, `delete-object` (type: "reminder").

### Smart Filters (updated 04/2026 — minimal set)

Pre-built filters alfred can use via `find-tasks` with `filterIdOrName`:

| Filter | Intent | Use |
|--------|--------|-----|
| 🎯 Big Tasks | `@prove` — all prove goals | Daily focus selection |
| 🏆 Milestones | Milestones section tasks | Roadmap checkpoint awareness |
| ⏰ Overdue | Overdue tasks | Safety net |

Energy-based filters removed (Deep Work Today, Medium Energy Today, Low Energy). Alfred can still query by label directly: `find-tasks` with `labels: ["high_energy"]`.

**Deleted labels:** chain_english, life, course
**Active labels:** high_energy, low_energy, medium_energy, creative, english, prove

### Filter Syntax Quick Reference

| Syntax | Meaning | Example |
|--------|---------|---------|
| `#Project` | Project only | `#⚔️ Main Quests` |
| `##Project` | Project + sub-projects | `##⚔️ Main Quests` |
| `/Section` | Section within any project | `/🏆 Milestones` |
| `@label` | Label | `@high_energy` |

**Common mistake:** `##🏆 Milestones` = project named "🏆 Milestones" (wrong). `/🏆 Milestones` = section (correct).
