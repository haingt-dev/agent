# Memories

This directory stores per-project memory files used by the agent hub for cross-project context.

## Structure

```
memories/
├── global/          # Global memories (shared across all projects)
│   └── MEMORY.md
├── <project>/       # Per-project memories
│   ├── MEMORY.md    # Memory index
│   └── *.md         # Individual memory files
```

## Privacy

Memory files contain personal context (behavioral patterns, career info, health data, financial snapshots) and are **gitignored** by default. They are never committed to the repository.

## How It Works

- Claude Code auto-memory (`~/.claude/projects/*/memory/`) manages per-project memories
- The hub's `memories/` directory provides a centralized view for cross-project skills
- Memory files are created/updated by Claude during conversations
- The `MEMORY.md` index in each directory links to individual memory files
