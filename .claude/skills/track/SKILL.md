---
name: track
description: "Time tracking via Google Calendar — start/stop timers as visual colored blocks on timeline."
argument-hint: "[start/stop/today]"
model: sonnet
disable-model-invocation: true
allowed-tools: mcp__todoist__find-tasks, mcp__claude_ai_Google_Calendar__gcal_list_events, mcp__claude_ai_Google_Calendar__gcal_create_event, mcp__claude_ai_Google_Calendar__gcal_update_event
---

# Track — Time Tracking

Track time spent on quests as Google Calendar events. Visual colored blocks on timeline. Use timezone Asia/Ho_Chi_Minh.

## Usage

```
/track                → today's tracked time summary
/track start [task]   → start tracking (create calendar event)
/track stop           → stop tracking (close current event)
/track today          → detailed report by quest type
```

## Calendar

**Calendar ID:** `418bf2dd3ad2961370acfd426343cbf3e7230575000d76897cbfd943e7f02d2d@group.calendar.google.com`

All time tracking events go to this calendar, separate from regular events.

## Color Mapping (quest type → Google Calendar colorId)

| Todoist Section (ID) | Quest Type | colorId | Color |
|---|---|---|---|
| Anchor Chain (`6g6f74jfm5VmhWG9`) | Daily Quests | `11` | Tomato |
| High Energy (`6g6f74h58rpwpv47`) | High Energy | `9` | Blueberry |
| Medium Energy (`6g6f74jhHXCVgxW7`) | Medium Energy | `7` | Peacock |
| Low Energy (`6g6f74jrXXg5Pp37`) | Low Energy | `2` | Sage |
| Milestones (`6g6h7Qfmj6MGFV97`) | Milestones | `9` | Blueberry |
| Passion (`6g6f74jRJwPPCmWp`) | Passion | `3` | Grape |
| Life (`6g6f74qmvFxphmJG`) | Life | `10` | Basil |

Fallback by projectId:
- `6g6f74gGg464CPv9` (Daily Quests) → colorId `11`
- `6g6f74cmqrRj2937` (Main Quests) → colorId `9`
- `6g6f74h9JQXGVX6p` (Side Quests) → colorId `10`

## Step 0: Parse Intent

Read `$ARGUMENTS` and user message:
- No args → **STATUS mode**
- "start" + description → **START mode**
- "stop" → **STOP mode**
- "today" / "hom nay" → **REPORT mode**

## STATUS mode

1. Call `gcal_list_events` on Time Tracking calendar for today (timeMin=00:00, timeMax=23:59, timeZone=Asia/Ho_Chi_Minh)
2. Calculate total tracked time from events
3. Show:
```
### Time Tracked — Today
| Quest | Time | Duration |
|---|---|---|
| CCNA study | 09:00 – 11:30 | 2h 30m |
| ELSA practice | 14:00 – 14:45 | 45m |
| **Total** | | **3h 15m** |
```

## START mode

1. Search Todoist: `mcp__todoist__find-tasks` with user's description as searchText
   - If found → get sectionId → look up colorId from mapping table
   - If not found → ask user which quest type, default to Blueberry (High Energy)

2. Check for open tracking: `gcal_list_events` today on Time Tracking calendar
   - An event is "active" if its end time is in the future (end > NOW). This catches the placeholder end (start + 1h) regardless of when the event was created — even if the user forgot to stop hours ago, as long as the placeholder hasn't passed yet.
   - If an active event is found → ask: "Dang tracking [event name] tu [start time]. Muon stop va start task moi khong?"
     - If user confirms → stop the active event (update end to NOW), then proceed to create new event
     - If user declines → abort, don't create overlapping events

3. Create event: `gcal_create_event`
   - `calendarId`: Time Tracking calendar ID
   - `event.summary`: task content (from Todoist)
   - `event.colorId`: from mapping table
   - `event.start.dateTime`: NOW in RFC3339 (Asia/Ho_Chi_Minh)
   - `event.end.dateTime`: NOW + 1h (placeholder — will be updated on stop)
   - `event.description`: `Todoist task: [task id] | Quest: [quest type]`
   - `event.reminders`: `{"useDefault": false}` (no reminders for tracking events)
   - `sendUpdates`: `none`

4. Show: `Started: [task] → [quest type] ([color name])`

## STOP mode

1. `gcal_list_events` today on Time Tracking calendar, most recent first
2. Find the active event using these checks in order:
   a. Any event whose end time is in the future (end > NOW) → active
   b. If none found, check for the most recently started event whose description contains "Todoist task:" — if it started within the last 8h and its duration is exactly 1h (the placeholder), it's likely an un-stopped session. Ask user: "Event [name] started at [time] — still tracking?"
   - If no active event found → "Khong co task nao dang tracking."
3. Update end time: `gcal_update_event`
   - `event.end.dateTime`: NOW
   - `sendUpdates`: `none`
4. Calculate duration = end - start
5. Show: `Stopped: [event summary] — [duration]`

## REPORT mode

1. `gcal_list_events` today on Time Tracking calendar
2. Group by colorId → quest type
3. Present:
```
### Time Report — [DD/MM/YYYY]

| Quest Type | Time | Entries |
|---|---|---|
| High Energy | 3h 15m | CCNA, Docker |
| Daily Quests | 45m | ELSA, Anki |
| Life | 30m | groceries |
| **Total** | **4h 30m** | |
```

## Rules

- Event summary = Todoist task content (no prefix needed — separate calendar handles isolation)
- Always use `sendUpdates: 'none'` — no email notifications for tracking events
- Always set `reminders.useDefault: false` — no popup/email reminders
- Format durations as `Xh Ym` (e.g., `2h 30m`, `45m`, `1h`)
- Do NOT modify Todoist tasks — this skill only creates/updates calendar events
- Do NOT auto-start timers — only start when user explicitly uses `/track start`
- Timezone: always Asia/Ho_Chi_Minh for all datetime operations
