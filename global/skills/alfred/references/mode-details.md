# Mode Details — Full Reference

Read when executing Mode 3, Mode 4, or Mode 5 for the detailed procedure.

---

## Mode 3: Cleanup Flow (Full Detail)

### Step C1: Fetch today's tasks + calendar

Parallel calls:
- `mcp__todoist__find-tasks-by-date` with startDate="today" (includes overdue)
- `gcal_list_events` for today — to identify `[alfred]` calendar-only blocks

### Step C2: Split into groups

```
### Reschedulable Quests
| # | Quest | Project / Section | Due |
|---|---|---|---|
| 1 | CCNA - Hoc 1h | Main / High | today |
| 2 | Rai CV & Research | Main / Medium | today |
```

Note: Daily habits (Anki, ELSA, Mini Output, Exercise) are calendar recurring events — not in Todoist, not part of cleanup.

### Step C3: Ask user

Use `AskUserQuestion`: "Tasks nào đã hoàn thành hôm nay?" — expect numbers, names, or "none".

### Step C4: Process

- Tasks user says done → `mcp__todoist__complete-tasks` (marked completed for real)
- Remaining reschedulable tasks → `mcp__todoist__reschedule-tasks` for each:
  - Recurring tasks: `reschedule-tasks` with `date` set to tomorrow → Todoist advances to next occurrence
  - Non-recurring tasks: ask user for target date, then `reschedule-tasks` with that date
- Daily habits → not in Todoist (calendar recurring events, skip)
- **Stale `[alfred]` calendar events from today** → `gcal_delete_event` to clean up materialized blocks that are no longer relevant
- **Recurring calendar events (has `recurringEventId`)** → NEVER delete. Past = already resolved. Only `[alfred]`-marked non-recurring blocks are safe to delete.
- **Todoist tasks materialized earlier today** → `reschedule-tasks` handles this — moves to next occurrence without overwriting the recurrence rule

**Important:** `reschedule-tasks` is the documented Todoist API for moving due dates. It preserves recurrence. After the call, verify the task's `due.date` advanced to the next occurrence.

### Step C5: Summary

> Read `references/output-formats.md` for the cleanup summary template.

### Cleanup Rules

- Daily habits are calendar recurring events — never create Todoist duplicates
- NEVER use `complete-tasks` for rescheduled tasks — use `reschedule-tasks`
- Only use `complete-tasks` for tasks the user confirms they actually did
- For non-recurring tasks, do NOT auto-reschedule — ask what date to move to
- Keep the interaction fast — one question max, then execute

---

## Mode 4: Materialization Detail (Steps 7-8)

### Step 7: Materialize to calendar (if today/tomorrow)

- **If task is for today or tomorrow AND schedule context is available:**
  1. Gather data: `gcal_list_events` + `find-tasks-by-date` for the target date
  2. Find optimal time slot using science engine (read `references/science-engine.md`)
     - If task has `duration` → allocate that exact duration
     - If no duration → use heuristic: 90m (high_energy), 45m (medium_energy), 30m (low_energy)
  3. Set timed due using **task IDs from step 6**:
     - Recurring: `reschedule-tasks` with `date: "YYYY-MM-DDTHH:MM:SS"`
     - Non-recurring: `update-tasks` with `dueString: "today at HH:MM"`
  4. If task has `deadlineDate` within 48h → flag ⚠️, confirm slot finishes before deadline
  5. Show both Todoist + Calendar changes
- **If task is for future date (beyond tomorrow):** Todoist only, no materialization

### Step 8: Show result

> Read `references/output-formats.md` for the task result table format.

---

## Mode 4: UPDATE Mode

### Step Q2 (UPDATE mode): Find & Modify

1. Search: `mcp__todoist__find-tasks` with text from user's message
2. Match selection:
   - 1 match → use it
   - Multiple matches → pick the most relevant by name similarity. If genuinely ambiguous, list top 3 and ask
   - 0 matches → tell user, suggest checking the task name
3. Apply changes via `mcp__todoist__update-tasks` — only include fields that need changing
4. Show before/after comparison as a table

---

## Mode 4: Handling Vague Tasks

If a task description is too vague to classify:
- Use whatever context is available from the conversation to infer intent
- Default to **Main Quests / 💰 Income, p2, medium_energy** — safest middle ground
- Mention your reasoning so the user can correct if wrong
- Never leave a task unclassified or put it in Inbox

---

## Duration Estimation Reference

| Task type | Default | Notes |
|-----------|---------|-------|
| Deep focus / building / prove-phase | `90m` | 1 ultradian cycle minimum |
| Reviews / coordination / planning | `45m` | Half cycle |
| Reading / passive learning | `30m` | Low cognitive load |
| Admin / errands / household | `30m` | Short, interruptible |
| User-specified | exact | Always trust user's estimate |

**Mode 2 (Optimize) reads duration:** If task has `duration` field → allocate exact. If absent → estimate from energy label using table above.

---

## Mode 5: Weekly Review Flow (Full Detail)

### Step R1: Determine Week Range

Parse `$ARGUMENTS`:
- No argument / "this week" / "tuần này" → current ISO week (Mon-Sun)
- "last week" / "tuần trước" → previous ISO week
- "W11" or "w11" → ISO week 11 of current year

Calculate via Bash:
```bash
# Current week
WEEK_START=$(date -d "monday this week" +%Y-%m-%d)
WEEK_END=$(date -d "$WEEK_START + 6 days" +%Y-%m-%d)
WEEK_LABEL=$(date -d "$WEEK_START" +%Y-W%V)
NOTE_PATH="10 Journal/Captures/${WEEK_LABEL}-Todos.md"

# Last week
WEEK_START=$(date -d "monday last week" +%Y-%m-%d)

# Specific week (e.g. W11)
WEEK_START=$(date -d "2026-01-01 +$((11-1)) weeks -$(date -d '2026-01-01' +%u) days +1 day" +%Y-%m-%d)
```

### Step R2: Fetch Data (parallel)

1. `mcp__todoist__find-completed-tasks` — `since: "{WEEK_START}T00:00:00"`, `until: "{WEEK_END}T23:59:59"`
2. `mcp__todoist__find-tasks-by-date` — `startDate: "{WEEK_START}"`, `days: 7` → active tasks due this week = carried over
3. `Read` — read weekly note at vault `{NOTE_PATH}`. If file not found → **STOP**, tell user: "Weekly note {WEEK_LABEL} chưa tồn tại. Tạo trước qua QuickAdd: Weekly Todo trong Obsidian."

### Step R3: Build & Propose

**Completed tasks** — group by project/section:
- ⚔️ Main Quests: Income / Growth / Family / Milestones
- 🎮 Side Quests: Passion / Life
- Sort by completion date within each group
- Skip recurring daily habits (Anki, ELSA, Mini Output, Exercise) — they clutter the review

**Carried over** — active tasks with due date in this week:
- Filter out recurring tasks whose due date already advanced past WEEK_END (auto-rescheduled by Todoist)
- Show with original due date

**Proposal** — show preview using format from `references/output-formats.md` (Weekly Review Format). Use `AskUserQuestion` with options: Approve / Modify / Cancel.

### Step R4: Patch Note

After approval:

1. Read current note body (everything below frontmatter) from the `Read` result in R2
2. Parse sections: find `## 📊 Review` and `## 📝 Notes`
3. Reconstruct full body:
   - Replace `## 📊 Review` section content with new review data
   - Keep `---` separator
   - Keep `## 📝 Notes` section content exactly as-is
4. Write via Obsidian CLI:

```bash
# Patch body (replaces everything below frontmatter, preserves frontmatter)
obsidian patch path="{NOTE_PATH}" content="{RECONSTRUCTED_BODY}"

# Update timestamp
obsidian property:set path="{NOTE_PATH}" name="updated" value="{NOW}" type=datetime

# Archive if reviewing past week
obsidian property:set path="{NOTE_PATH}" name="status" value="archived" type=text
```

Get current timestamp via: `obsidian eval 'code=new Date().toLocaleString("sv-SE",{timeZone:"Asia/Ho_Chi_Minh"}).replace("T"," ").substring(0,16)'`

**Status logic:**
- Reviewing past week (WEEK_END < today) → `status: archived`
- Reviewing current week with carried over tasks → keep `status: in_progress`

### Step R5: Summary

> Read `references/output-formats.md` for the summary template.

Show: completed count, carried over count, note path updated.

---

## Mode 3 Sub-Mode: Audit Flow

Triggered by "audit", "health check", "kiểm tra". Full Todoist structure verification against expected project hierarchy.

### Step A1: Fetch Structure (parallel)

- `find-sections` for Main Quests (`6g6f74cmqrRj2937`) — verify 4 sections (💰 Income, 🧠 Growth, 👨‍👩‍👧 Family, 🏆 Milestones)
- `find-sections` for Side Quests (`6g6f74h9JQXGVX6p`) — verify 2 sections (🎯 Passion, 🏠 Life)
- `find-tasks` per section — count and list all active tasks
- `find-tasks` with filter `created before: -30 days & no date & !recurring` — stale tasks
- `find-tasks` with filter `!@high_energy & !@medium_energy & !@low_energy` — unlabeled tasks

### Step A2: Health Checks

| Check | How | Flag if |
|-------|-----|---------|
| Sections exist | Compare A1 sections vs SKILL.md reference IDs | Missing section → ⚠️ MISSING |
| Milestones populated | Count tasks in 🏆 Milestones | 0 tasks → ⚠️ EMPTY |
| Deadline coverage | Milestones without `deadlineDate` | Missing → ⚠️ NO DEADLINE |
| Stale tasks | >30 days, no date, not recurring | Present → 🧹 STALE |
| Priority drift | Main Quest tasks with p3/p4, Side Quest with p1 | Wrong tier → ⚠️ PRIORITY |
| Label hygiene | Tasks missing energy label | Missing → ⚠️ NO LABEL |
| Duration set | Tasks without `duration` field | Missing → 💡 NO DURATION |

### Step A3: Report

```
🏥 Todoist Health Audit — {date}

✅ Healthy: {passing checks}
⚠️ Issues:
  → {check}: {details + affected tasks}

🔧 Suggested fixes:
  → {actionable fix per issue}
```

### Step A4: Execute

`AskUserQuestion`: "Fix nào muốn Alfred thực hiện?" — options: Fix all / Pick specific / Cancel.

For each approved fix:
- Missing deadlines → `update-tasks` with `deadlineDate`
- Priority drift → `update-tasks` with correct priority
- Missing labels → `update-tasks` with suggested energy label
- Missing duration → `update-tasks` with estimated duration (90m/45m/30m by energy)
- Stale tasks → offer: schedule (set due), complete, or delete
