# Brain: Indie Game Dev Infrastructure Ecosystem

This context is shared across all projects in Hải's indie ecosystem. If you're reading this, you're working on an ecosystem project — frame advice and decisions within this thesis.

## Ecosystem Thesis

Make things people want to play. Share tools and learnings freely. Help others on the same path.
- Backend (7 years) + AI + video + game dev — all skills serve making games
- Every tool/asset built for Wildtide → shared with other indie devs
- Wildtide (roguelike city builder, Godot) = center of gravity, PRIMARY BUILD

## Ecosystem Projects

| Project | Role in ecosystem |
|---------|------------------|
| `digital-identity` | Profile center — source of truth about Hải for AI systems |
| `portfolio` | Public-facing presence — haingt.dev (Astro + Cloudflare Pages) |
| `Wildtide` | Center of gravity — PRIMARY BUILD, roguelike city builder (Godot). Active development, post-pivot |
| `Bookie` | Community (9+ years) — video production pipeline |

## Cross-Project Conventions

- Handle: `haingt-dev` (GitHub, LinkedIn), `haingt_dev` (X), `haingt.dev` (Instagram, Facebook)
- Domain: `haingt.dev`
- Builder identity: "Independent Builder", not "freelancer" or "consultant"
- Career details, roadmap, freedom number → loaded via global CLAUDE.md (@goals.md, @personality.md)

## Memory Architecture

- **Auto-memory** (MEMORY.md per project): project-specific gotchas and decisions
- **Engram** (MCP): cross-project searchable history + session lifecycle
- **This brain file**: shared ecosystem context — one file, all ecosystem projects see it
- Don't duplicate ecosystem knowledge into per-project MEMORY.md — keep it here
