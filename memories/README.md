# Memories

Auto-memory storage for all Claude Code projects in `~/Projects/`.

## How it works

`~/.claude/projects/<slug>/memory` is symlinked INTO the matching subdir here. Claude Code reads/writes `MEMORY.md` + feedback files through the symlink; the canonical bytes live in this repo.

```
memories/
└── <project>/       # Symlink target from ~/.claude/projects/<slug>/memory
    ├── MEMORY.md    # Memory index
    └── *.md         # Individual memory files (feedback, gotchas, decisions)
```

Empty subdirs (e.g., projects with no auto-memory yet) are placeholders — **do not delete**. Removing a subdir breaks auto-memory for that project until Claude recreates the link.

## Privacy

Memory files contain personal context (behavioral patterns, career info, health data, financial snapshots) and are **gitignored** by default. They are never committed to the repository.
