---
name: research
disable-model-invocation: false
description: "Multi-source research and decision intelligence"
argument-hint: "[topic] [--deep] OR [A vs B] OR [validate: plan/idea]"
model: sonnet
allowed-tools: >
  Read, Glob, Grep, AskUserQuestion,
  WebSearch, WebFetch,
  Bash(chub *),
  mcp__claude_ai_Context7__resolve-library-id,
  mcp__claude_ai_Context7__query-docs,
  mcp__haingt-brain__brain_recall,
  mcp__haingt-brain__brain_save,
  mcp__haingt-brain__brain_graph,
  mcp__haingt-brain__brain_tools
---

# Research — Multi-Source Decision Intelligence

Systematic research pipeline that gathers evidence from multiple sources before forming a recommendation. Every verdict is filtered through Hai's roadmap, career anchors, and current phase capacity.

This skill exists because Claude's training data alone is insufficient for decisions that depend on current market state, personal context, or accumulated past decisions. The pipeline forces evidence-based answers by checking what Hai already knows (brain + Readwise) before hitting the web, then contextualizing findings against who Hai is and where he's headed.

**Design principles:**
- **Evidence over opinion** — gather first, synthesize second, recommend last
- **Cost discipline** — cheap sources first (brain → chub → Context7 → Web). Don't burn tokens on web searches when the answer is already cached
- **Clear stance** — no "it depends." State a position with reasoning. If evidence is genuinely split, say so and explain which side you lean toward and why
- **Profile-aware** — a technically correct answer that conflicts with Hai's roadmap, values, or capacity is still wrong for him right now

## Pre-flight

Run once per session, not per invocation:

1. `brain_recall("roadmap phase brick capacity")` — determine:
   - Active brick (which Prove slot is occupied)
   - Current phase (0 Pre-Baby / 1 Survival / 2 Stabilize / 3 Build)
   - Capacity level
2. `brain_recall("career anchors goals priority")` — load career anchors and priority framework
3. If brain results are thin or stale → fall back to reading `profile/roadmap.md` and `profile/goals.md`

These data points drive the Profile Filter step in every research run.

**Project scoping:** Auto-detect project from cwd (directory name under `~/Projects/`). Pass `project` parameter on brain_recall/brain_graph when researching project-specific topics. Omit for general topics (career, market, tooling).

## Mode Routing

Parse `$ARGUMENTS` to detect mode:

| Pattern | Mode | Purpose |
|---------|------|---------|
| `vs`, `or`, `so sánh`, `nên dùng`, `which`, `A vs B` | **Compare** | Head-to-head with verdict |
| `validate`, `critique`, `good idea`, `should I`, `có ổn không`, `is this` | **Validate** | Adversarial — find failure modes |
| _(everything else)_ | **Investigate** (default) | Open-ended research + recommend |

If arguments are empty or unclear → `AskUserQuestion`: "What do you want to research?"

---

## Pipeline

All three modes follow the same 8-step pipeline. The difference is in Step 6 (output format).

### Step 1: Parse

Extract from `$ARGUMENTS` and conversation context:
- **Topic**: the subject to research
- **Mode**: investigate / compare / validate (see routing table above)
- **Depth**: standard (default) or deep (`--deep` flag, or auto-triggered when sources conflict or topic includes "latest", "current", "2026")

### Step 2: Cache Check

Search brain for prior research on this topic with precise filtering:

```
brain_recall(query="research [topic]", type="discovery", time_range="-30 days")
```

Using `type="discovery"` avoids noise from session summaries or entity records. The `time_range` ensures only recent findings surface — stale research (>30 days) is treated as absent.

If a result exists:
- Surface the cached findings
- `AskUserQuestion`: "Found prior research from [date]. Use cached findings, or run fresh research?"
- If cached is accepted → skip to Step 6 (output) with cached data
- If fresh → continue pipeline

This step prevents re-doing expensive web research on topics already investigated recently.

### Step 3: Gather

Run these in parallel where possible — they are independent data sources.
Cost hierarchy: brain (free) → chub (local, fast) → Context7 (cloud) → Web (expensive).

**3a. brain** — past decisions and context beyond exact cache hit:
```
brain_recall("[topic variations]")
brain_recall("[broader context]")
```
Look for: related decisions, past trade-off analysis, any prior art. Readwise knowledge worth keeping should already be here via `/inbox`.

**3a+. brain_graph + brain_tools** (conditional — skip both if topic is new to brain or non-technical):

Only run these when the **cache check (Step 2) found prior research** or the topic involves **tools/libraries/workflows**. When the brain is sparse for a topic, these steps return noise that dilutes synthesis quality. Better to spend that attention budget on deeper web research and sharper profile filtering.

- `brain_graph(entity="[prior-research-id or topic]", depth=2)` — traverse relationships from prior findings. Surfaces chains like: decision → pattern → related discovery. Only valuable when a starting node exists.
- `brain_tools(query="[topic]", k=3)` — check if an existing tool/skill already handles this. If found → mention it: "Note: `[tool/skill]` may already handle this." Skip for career/market/personal decisions.

**3b. chub** (conditional) — only when the topic involves a library, framework, or SDK:
```bash
chub search "[library]" --json    # find available docs
chub get [doc-id] --lang py       # fetch curated doc content
```
chub provides curated, versioned, LLM-optimized docs — more reliable than raw web scraping for API specifics.
If chub has coverage → prefer it over Context7 for the same library (local, no cloud round-trip).
Skip for non-library topics (pricing strategy, market trends, career decisions).

**3c. Context7** (conditional) — cloud doc fallback when chub lacks coverage:
```
resolve-library-id(libraryName="[library]")
query-docs(libraryId="[resolved-id]", topic="[specific question]")
```
Use when: topic names a library/framework AND chub returned no results or insufficient depth.
Skip entirely for non-library topics.

**3d. WebSearch** — current state of the world:
- Standard depth: 2-3 targeted queries
- Deep: 4-5 queries with different angles (technical, community, market, comparison)
- Focus queries on: best practices, recent developments (2025-2026), community consensus, known pitfalls
- For promising results where the snippet is insufficient → `WebFetch` the full page (max 2-3 fetches)

### Step 4: Synthesize

Organize raw findings into:
- **Facts**: hard data with sources and dates
- **Consensus**: what most sources agree on
- **Contradictions**: where sources disagree — flag these explicitly
- **Recency**: how fresh each finding is (a 2024 benchmark may be outdated)
- **Gaps**: what the research couldn't answer

### Step 5: Profile Filter

Apply these filters to the synthesized findings. This is what makes the research non-generic:

1. **Career Anchors**: Does this align with Autonomy/Independence, Entrepreneurial Creativity, Lifestyle? If it conflicts → flag (don't silently drop — Hai should see the conflict)
2. **Active Brick**: Does this serve the current Prove slot? Or is it a distraction?
3. **Phase Capacity**: Is this feasible at current capacity? A 200-hour migration during Phase 1 (40% capacity, newborn) is a non-starter
4. **Ecosystem Coherence**: Does this serve the indie game dev infrastructure thesis? Or is it a tangent?
5. **Financial Viability**: Does this require spend that the survival budget can't absorb?

If a finding is technically correct but misaligned → include it in output with a clear flag: "Good approach, but conflicts with [specific constraint]."

### Step 6: Output

Format varies by mode. See Output Formats section below.

### Step 7: Auto-Save

Save findings automatically after presenting output — no gate, no confirmation needed.

```
brain_save(
  content: "Research: [topic] — [verdict]. Key evidence: [1-2 lines]. Profile: [alignment]. Sources: [count]"
  type: "discovery"
  tags: ["research", "[topic-tag]", "[mode]"]
  project: [auto-detected or null]
  metadata: {
    "source": "research",
    "confidence": "high|medium|low",
    "mode": "investigate|compare|validate",
    "source_count": N,
    "freshest_source": "YYYY-MM-DD"
  }
  relations: [if prior research on same topic found in Step 2]
    {target_id: "[prior-memory-id]", relation_type: "supersedes"}
)
```

**Relations logic:** If Step 2 found a cached finding that was overridden (user chose fresh research), save the new finding with `supersedes` relation pointing to the old one. This builds a research history chain navigable via `brain_graph`.

**Confidence mapping:** HIGH = 3+ concordant sources, recent data. MEDIUM = mixed signals or limited sources. LOW = single source, dated, or speculative.

Append to output: `Saved to brain: "[topic] — [verdict]" (confidence: [level])`

Hải can remove later with `brain_forget` if the finding turns out to be noise.

---

## Output Formats

### Investigate

```
## Research: [Topic] — [date]

### Context
Sources: [N brain / N chub / N context7 / N web]
Freshness: [newest source date]

### Key Findings
- [Finding 1] — [source type + date]
- [Finding 2] — [source type]
- [Contradiction: source A says X, source B says Y] — [both sources]

### Profile Fit
- Roadmap: [SERVES brick X / DISTRACTS from brick X / NEUTRAL]
- Phase [N] capacity: [feasible / too heavy for current phase]
- Career anchors: [ALIGNED / CONFLICTS with autonomy|creativity|lifestyle]

### Recommendation
**[VERDICT]** — [2-3 sentences. Clear position. State what to do and why.]

### If Wrong
[1-2 sentences: the biggest risk to this recommendation. What evidence would change the verdict?]

### Sources
- [Title — URL or type — date]
```

### Compare

Same structure but replace "Key Findings" with a comparison table:

```
### Comparison: [A] vs [B]

| Dimension | [A] | [B] |
|-----------|-----|-----|
| [Core strength] | | |
| [Weakness] | | |
| Ecosystem fit | | |
| Learning curve | | |
| Community/support | | |
| Cost | | |

**Winner: [A or B]** — [reason in one line]
```

Keep Profile Fit + Recommendation + If Wrong sections.

### Validate

Same structure but add before Recommendation:

```
### Failure Modes
1. [Specific scenario where this plan/idea fails — with evidence]
2. [Market/timing risk]
3. [Execution risk given current phase/capacity]

### Confidence
**[HIGH / MEDIUM / LOW]** — based on: [N evidence points, source quality, recency]
```

---

## Rules

- **Always take a stance.** "It depends" is not a verdict. If evidence is genuinely split 50/50, say which side you lean toward and why. Hai can override — but he needs a starting position to react to.
- **Cheap sources first.** brain → chub → Context7 → WebSearch. If the answer exists locally, don't burn web tokens.
- **No subagents.** All research runs inline. Subagents add latency and token cost without meaningful benefit for interactive research.
- **chub before Context7.** For library/framework docs, check `chub search` first — it's local and curated. Only fall back to Context7 when chub has no coverage for the library.
- **WebFetch is targeted.** Only fetch full pages when a search snippet is clearly incomplete and the full content is load-bearing for the verdict. Max 2-3 fetches per run.
- **Profile filter informs, not censors.** If something is technically good but contextually wrong for Hai right now, include it with a clear flag. Don't silently drop findings.
- **Auto-save, no gate.** Save findings to brain automatically after output. Report what was saved. Hải can `brain_forget` if it's noise — less friction than asking every time.
- **Concise output.** Decision brief should be scannable — 60-80 lines target. Raw source material never goes verbatim into output.
- **When to use Opus.** For complex decisions with many conflicting sources, or high-stakes architectural choices, consider switching to Opus before invoking `/research`. The skill runs on whatever model is active — Sonnet handles 90% of cases, Opus is worth it for the hard 10%.
