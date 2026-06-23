---
name: godot-status
description: "Check or initialize a project's docs/STATUS.md status dashboard."
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
| (none) / `check` [`--strict`] | "where's this project at", `/godot-status`, pre-commit | Read STATUS.md + reconcile with live reality + report. `--strict` exits non-zero on stale/missing — for git hooks. |
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

### Derived vs judged (why it doesn't rot)

A hand-kept dashboard rots when it mixes two kinds of field. Keep them separate (borrowed from IronCradle's
derive-from-code board):

- **Derived** — the machine owns these: `updated`, the Tests line, the Code-counts line, git-derived bits.
  `update` writes them, `check` verifies them. Never hand-maintain them; they come from reality.
- **Judged** — only a human sets these: `phase`, `health`, `milestone`, **Now** (next action + blockers), the
  Design-readiness narrative. The repo can't infer them.

`check` reconciles the judged claims against the derived reality and flags the gap. That split — machine-truth vs
human-judgment — is what keeps the board honest without a heavyweight generator.

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

### Enforcing freshness — `check --strict` + pre-commit

A board only stays honest if something *forces* it. `--strict` runs the bundled `scripts/status_check.py` — a
plain, dependency-free check (STATUS.md exists + its `updated` isn't older than the newest **code** commit) that
exits non-zero when stale. Claude can't run inside a git hook, so this script is the enforceable half (mirrors
IronCradle's `derive_status.py --check`). Wire it into a repo via `init` (it copies the script to `tools/` and adds):

```yaml
# .pre-commit-config.yaml
- repo: local
  hooks:
    - id: status-fresh
      name: STATUS.md is fresh
      entry: python3 tools/status_check.py
      language: system
      pass_filenames: false
```

Then any commit that changes code without bumping STATUS.md fails until you run `update`. That is the anti-rot guarantee.

## Mode: init

For a repo with no STATUS.md. Aim for a *useful first draft from what the repo already knows* — not a blank template.

1. Refuse to overwrite an existing `docs/STATUS.md` (point the user at `check` / `update`).
2. Detect `type`: `project.godot` → `godot-<version>`; `package.json` → node/framework; `pyproject.toml`/`*.csproj` → etc. Fall back to `unknown`.
3. Mine existing signals: `docs/README.md`, `docs/progress.md`, `.memory-bank/*`, `CLAUDE.md` / `AGENTS.md`, git log, and `brain_recall` for phase/roadmap.
4. Write `docs/STATUS.md` in the convention, pre-filled from those signals.
5. Where the repo can't tell you (true phase, the real next action, health), insert an explicit `<!-- TODO: confirm -->` so the human makes the judgment call. An honest gap beats a confident guess.
6. Tell the user what you inferred vs. left as TODO, and suggest linking STATUS.md from `docs/README.md`.
7. Offer to enable enforcement: copy the bundled `scripts/status_check.py` to the repo's `tools/status_check.py`
   and add the pre-commit hook above, so STATUS.md can't silently fall behind code. Skip cleanly if the repo has
   no pre-commit setup and the user doesn't want one.

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
- **Enforcement vs. report split** (from IC): the rich reconcile + judgment is this skill (needs Claude); the
  deterministic freshness gate is `scripts/status_check.py` (runs in pre-commit, no Claude). Heavy per-system
  auto-generation (IC's `systems.toml` + a generator) is deliberately NOT ported — it only pays off at
  many-systems scale; add it per-project later if a project outgrows the hand-kept board.
- Never invent test results, counts, or a phase. An honest "unknown / no tests yet" is more useful than a confident wrong number.
