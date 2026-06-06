---
name: godot-status
description: "Check or initialize a project's standardized status dashboard at docs/STATUS.md. Use whenever the user asks 'where is this project at', 'check status', 'project status', 'what's the state / what's next here', or runs /godot-status — and to set up status tracking the first time (init) on a repo with no STATUS.md. Reads the STATUS.md convention and reconciles it against live git / tests / code / memory so the dashboard never silently goes stale. Godot-aware (engine version, GUT) but works on any repo. Reach for it even when the user only implies they want a state-of-the-project readout."
model: sonnet
allowed-tools: Read, Write, Edit, Glob, Grep, Bash(git *), Bash(find *), Bash(wc *), Bash(godot *), mcp__haingt-brain__brain_recall
---

# Godot Status

A consistent way to **save** and **check** where a project stands. Every project keeps one dashboard file —
`docs/STATUS.md` — in a fixed format, so status lives in the same place with the same shape everywhere, and a
glance (or this skill) answers: what phase, what's next, and do the docs still match reality.

Three modes, chosen from the argument (default = `check`):

| Arg | When | What it does |
|-----|------|--------------|
| (none) / `check` | "where's this project at", `/godot-status` | Read STATUS.md + reconcile with live reality + report |
| `init` | repo has no STATUS.md yet | Scaffold STATUS.md from what the repo already knows |
| `update` | after real progress, or from `/wrap` | Refresh the auto/machine fields; leave human prose |

If `docs/STATUS.md` is missing and the user didn't say `init`, say so and offer `init` — don't fabricate a dashboard.

## The `docs/STATUS.md` convention (the standard — same everywhere)

Half machine-readable (YAML frontmatter this skill parses), half human dashboard (the body). Keeping the
frontmatter keys stable is what makes the check deterministic and lets a future tool query many projects at once.
Scaffold and read EXACTLY these keys:

```markdown
---
project: <repo-name>
type: <godot-4.x | node | astro | python | ...>
phase: <pre-production | active-dev | paused | shipped>
health: <green | yellow | red>
milestone: <current milestone id, e.g. M0-art-gate>
updated: <YYYY-MM-DD>
---

# <Project> — Status

> **Phase:** <phase> · **Health:** 🟢/🟡/🔴 · **Updated:** <YYYY-MM-DD>

## Now
- **Next action:** <the single most concrete next step>
- **Blockers:** <what's in the way, or "none">

## Design readiness
<🟢/🟡/🔴 per area, or a one-liner pointing at docs/README.md / the design vault>

## Build readiness
- **Milestone:** <current milestone + a word on progress>
- **Tests:** <green/red + count, or "none yet">
- **Code:** <1–2 lines: what actually exists>

## Links
- GDD: <docs/gameDesign.md or n/a> · Progress: <docs/progress.md or n/a> · Vault: <external link or n/a>
```

Why this shape: `STATUS.md` is the **at-a-glance dashboard**. Detailed milestones live in `docs/progress.md`; the
doc map lives in `docs/README.md`. STATUS **summarizes and links** — it must not duplicate them, or the copies
drift. `health` is a fast traffic-light; `phase` / `milestone` / `updated` are the fields a cross-project query reads.

## Mode: check (default)

A hand-written dashboard rots, so the value of `check` is reconciling it against the repo — never trusting it blindly.

1. Read `docs/STATUS.md`. (Missing → tell the user, offer `init`, stop.)
2. Gather live reality:
   - **Git:** current branch, `git status --porcelain` (dirty?), `git log --oneline -5`, ahead/behind upstream if one exists.
   - **Tests (Godot/GUT):** if `addons/gut/` exists, run headless and capture pass/fail counts
     (`godot --headless -s addons/gut/gut_cmdln.gd -gexit`); otherwise note "no test framework" — never invent results.
   - **Code reality:** rough counts — `*.tscn` scenes, `*.gd` scripts, `addons/` present (find/wc).
   - **Engine:** read the Godot version from `project.godot` (`config_version` / `application/config/features`).
   - **Memory:** `brain_recall` the project's phase / roadmap / recent decisions.
3. Produce the report (below).
4. **Flag divergence and staleness — the most valuable part:**
   - Divergence: STATUS says `milestone: M2` but git/code shows M2 merged (or vice-versa) → call it out.
   - Staleness: `updated` is well before the last commit date → "STATUS.md is N days behind the last commit; run `update`."

### Report format

```
<Project> — <phase> · <health emoji>
Next: <next action>     Blockers: <…>

Build:  <milestone> · tests <X/Y green | none> · <N scenes, M scripts> · Godot <ver>
Git:    <branch> · <clean | N uncommitted> · <ahead/behind>
Design: <readiness one-liner>

⚠ <divergence / staleness flags, or "STATUS.md matches reality">
```

Keep it scannable. The reader wants the phase, the next action, and "do the docs lie?" in five seconds.

## Mode: init

For a repo with no STATUS.md. Aim for a *useful first draft from what the repo already knows* — not a blank template.

1. Refuse to overwrite an existing `docs/STATUS.md` (point the user at `check` / `update`).
2. Detect `type`: `project.godot` → `godot-<version>`; `package.json` → node/framework; `pyproject.toml`/`*.csproj` → etc. Fall back to `unknown`.
3. Mine existing signals: `docs/README.md`, `docs/progress.md`, `.memory-bank/*`, `CLAUDE.md` / `AGENTS.md`, git log, and `brain_recall` for phase/roadmap.
4. Write `docs/STATUS.md` in the convention, pre-filled from those signals.
5. Where the repo can't tell you (true phase, the real next action, health), insert an explicit `<!-- TODO: confirm -->` so the human makes the judgment call. An honest gap beats a confident guess.
6. Tell the user what you inferred vs. left as TODO, and suggest linking STATUS.md from `docs/README.md`.

## Mode: update

After real progress, or called by `/wrap` at session end.

1. Read STATUS.md. Recompute the **auto/machine fields** from reality: `updated` (today), `milestone` (if clearly advanced), the Tests line, the Code line, git-derived bits.
2. Leave **human prose** (Next action, Blockers, Design-readiness narrative) untouched unless the user asks — those are judgment calls, not auto-derivable.
3. Show a short diff of what changed.

## Notes

- **Degrade gracefully off Godot.** The convention plus the git/memory logic are generic; only the engine-version
  parse and the GUT run are Godot-specific — skip them cleanly on a non-Godot repo. (This keeps a future move to an
  all-projects plugin painless.)
- **Complements `check-gdd`, doesn't replace it.** `check-gdd` deep-compares code against the design doc;
  `godot-status` is the fast dashboard across git / tests / docs / memory.
- Never invent test results, counts, or a phase. An honest "unknown / no tests yet" is more useful than a confident wrong number.
