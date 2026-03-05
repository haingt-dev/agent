---
name: quest
description: "Add or update Todoist tasks with smart classification into quest system. Classifies by energy level, priority, and project automatically."
argument-hint: "[add/update task description]"
model: sonnet
allowed-tools: mcp__todoist__add-tasks, mcp__todoist__find-tasks, mcp__todoist__update-tasks
---

# Quest — Smart Task Management

Add or update tasks with automatic classification into the quest system.

## Usage

```
/quest thêm task học Docker, mua sữa cho vợ
/quest sửa CCNA priority p1
```

## Todoist Structure Reference

### Projects & Section IDs

**🔥 Daily Quests** (`6g6f74gGg464CPv9`)
- 🔗 Anchor Chain (`6g6f74jfm5VmhWG9`) — recurring daily habits only (Anki, ELSA)

**⚔️ Main Quests** (`6g6f74cmqrRj2937`)
- 🧠 High Energy (`6g6f74h58rpwpv47`) — deep work, career, study, build
- ⚡ Medium Energy (`6g6f74jhHXCVgxW7`) — coordination, reviews, moderate work
- 🌊 Low Energy (`6g6f74jrXXg5Pp37`) — passive learning, reading, listening
- 🏆 Milestones (`6g6h7Qfmj6MGFV97`) — goals/OKRs with target dates

**🎮 Side Quests** (`6g6f74h9JQXGVX6p`)
- 🎯 Passion (`6g6f74jRJwPPCmWp`) — personal projects, creative work, side business
- 🏠 Life (`6g6f74qmvFxphmJG`) — admin, errands, purchases, household, appointments

### Labels

| Label | When to apply |
|-------|---------------|
| `english` | English/language learning |
| `career` | Professional development, job-related |
| `creative` | Design, writing, video, art, building |
| `life` | Personal life management |
| `chain_english` | Anchor Chain habit only (Anki/ELSA) |
| `high_energy` | Requires peak focus |
| `low_energy` | Doable when tired |

### Priority Convention

The Todoist MCP uses p1=highest through p4=lowest, matching these conventions directly. Pass `priority: 1` for p1, `priority: 2` for p2, etc.

| Priority | Usage |
|----------|-------|
| p1 | Anchor Chain habits ONLY — reserved exclusively for recurring daily habits in Daily Quests. Never assign p1 to other tasks, even important ones. |
| p2 | Main Quests — important, career/life impact |
| p3 | Side Quests — optional but regular |
| p4 | Rewards, low-priority backlog |

## Step 0: Parse Intent

Read `$ARGUMENTS` and the user's message:
- Keywords "thêm", "add", "tạo", or a list of tasks → **ADD mode**
- Keywords "sửa", "update", "chuyển", "đổi", "move" → **UPDATE mode**

## Step 1 (ADD mode): Classify & Create

For each task, classify using this decision tree:

**1. Which project + section?**

| Ask yourself | If YES → | Priority |
|---|---|---|
| Is this a recurring daily habit? | Daily Quests / Anchor Chain | p1 |
| Requires deep focus, career growth, study, building? | Main Quests / High Energy | p2 |
| Requires coordination, reviews, moderate effort? | Main Quests / Medium Energy | p2 |
| Passive learning, reading, watching, light research? | Main Quests / Low Energy | p2 |
| Goal-level item with a target date (OKR, milestone)? | Main Quests / Milestones | p2 |
| Personal/creative project, side business? | Side Quests / Passion | p3 |
| Life admin, errands, purchases, household? | Side Quests / Life | p3 |

**2. Labels?** Apply ALL that match from the Labels table above.

**3. Due date?**
- "hôm nay" / "today" → `dueString: "today"`
- "ngày mai" / "tomorrow" → `dueString: "tomorrow"`
- Specific date mentioned → parse to dueString
- Nothing mentioned → no due date

**4. Create tasks:**
- Call `mcp__todoist__add-tasks` with ALL tasks in a single batch call
- Each task must have: `content`, `projectId`, `sectionId`, `priority`, `labels`
- Include `description` if user provided extra context
- Include `dueString` if date was mentioned

**5. Show result** with classification reasoning:
```
### Tasks Created
| Task | Project / Section | Priority | Labels |
|------|-------------------|----------|--------|
| học Docker | Main / 🧠 High Energy | p2 | career |
| mua sữa cho vợ | Side / 🏠 Life | p3 | life |
```

### Few-shot Examples

- "setup personal branding" → Main / High Energy, p2, [career, creative]
- "setup iPad for light work" → Side / Life, p3, [life]
- "học Docker" → Main / High Energy, p2, [career]
- "đọc sách Atomic Habits" → Main / Low Energy, p2, [low_energy]
- "làm portfolio website" → Side / Passion, p3, [creative]
- "mua sữa cho vợ" → Side / Life, p3, [life]
- "review PR từ team" → Main / Medium Energy, p2, [career]
- "setup project học tiếng Anh" → Main / High Energy, p2, [english, career]

## Step 1 (UPDATE mode): Find & Modify

1. Search: `mcp__todoist__find-tasks` with text from user's message
2. Match selection:
   - 1 match → use it
   - Multiple matches → pick the most relevant by name similarity. If genuinely ambiguous, list top 3 and ask
   - 0 matches → tell user, suggest checking the task name
3. Apply changes via `mcp__todoist__update-tasks` — only include fields that need changing:
   - Section move: update `sectionId` (look up target ID from the Structure Reference above)
   - Priority change: update `priority`
   - Label change: update `labels`
   - Content edit: update `content`
   - Due date: update `dueString`
4. Show before/after comparison as a table:
```
| Field | Before | After |
|-------|--------|-------|
| Section | High Energy | Medium Energy |
```

## Handling Vague Tasks

If a task description is too vague to classify (e.g., "do stuff", "handle that thing"):
- Use whatever context is available from the conversation to infer intent
- Default to **Main Quests / Medium Energy, p2** — it's the safest middle ground
- Mention your reasoning so the user can correct if wrong
- Never leave a task unclassified or put it in Inbox — a wrong classification is better than no classification (user can always fix it with `/quest sửa`)

## Rules

- Do NOT ask user to confirm classification — make the call, show your reasoning
- If user explicitly specifies project/priority/labels → override the decision tree
- Batch create: always 1 API call for all tasks, never one-by-one
- NEVER put tasks in Inbox — always classify into a project/section
