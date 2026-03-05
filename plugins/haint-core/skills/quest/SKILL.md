---
name: quest
description: Add or update Todoist tasks with smart classification into quest system
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

| Priority | Usage |
|----------|-------|
| p1 | Daily recurring habits only (Anchor Chain) |
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

1. Search for the task using `mcp__todoist__find-tasks` with text from user's message
2. If multiple matches, pick the most relevant one (or list and ask)
3. Apply the requested changes via `mcp__todoist__update-tasks`
4. Show before/after comparison

## Rules

- Do NOT ask user to confirm classification — make the call, show your reasoning
- If user explicitly specifies project/priority/labels → override the decision tree
- Batch create: always 1 API call for all tasks, never one-by-one
- NEVER put tasks in Inbox — always classify into a project/section
