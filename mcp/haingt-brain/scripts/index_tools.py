#!/usr/bin/env python3
"""Index all MCP tools, skills, and CLI tools into haingt-brain Semantic Toolbox.

Skills are auto-discovered from filesystem:
  ~/.claude/skills/*/SKILL.md → global (project=None)
  ~/Projects/*/.claude/skills/*/SKILL.md → project-scoped

MCP tools and CLI tools are manually curated (stable, descriptions need curation).

Usage: uv run python scripts/index_tools.py
"""

import json
import re
import sys
from pathlib import Path

# Add project to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from haingt_brain.db import connect, init_schema
from haingt_brain.tools.save import brain_save
from haingt_brain.tools.forget import brain_forget

# ── MCP Tool Definitions ────────────────────────────────────────────────────
# Manually curated. Each entry: (mcp_server, tool_name, description, category)

MCP_TOOLS = [
    # Google Calendar (claude.ai connector — names verified live 2026-06-12)
    ("claude_ai_Google_Calendar", "create_event", "Create a new event on Google Calendar with title, time, attendees, and description", "calendar"),
    ("claude_ai_Google_Calendar", "delete_event", "Delete an event from Google Calendar by event ID", "calendar"),
    ("claude_ai_Google_Calendar", "get_event", "Get details of a specific Google Calendar event by ID", "calendar"),
    ("claude_ai_Google_Calendar", "list_calendars", "List all available Google Calendars", "calendar"),
    ("claude_ai_Google_Calendar", "list_events", "List events from Google Calendar with optional date filtering", "calendar"),
    ("claude_ai_Google_Calendar", "respond_to_event", "Accept, decline, or tentatively accept a Google Calendar event", "calendar"),
    ("claude_ai_Google_Calendar", "suggest_time", "Suggest available meeting times / find free slots on Google Calendar", "calendar"),
    ("claude_ai_Google_Calendar", "update_event", "Update an existing Google Calendar event", "calendar"),

    # Gmail (claude.ai connector — names verified live 2026-06-13)
    ("claude_ai_Gmail", "search_threads", "Search Gmail threads using query syntax", "email"),
    ("claude_ai_Gmail", "get_thread", "Read an entire Gmail thread by thread ID", "email"),
    ("claude_ai_Gmail", "create_draft", "Create a draft email in Gmail with recipients, subject, and body", "email"),
    ("claude_ai_Gmail", "list_drafts", "List draft emails in Gmail", "email"),
    ("claude_ai_Gmail", "list_labels", "List all labels in Gmail", "email"),
    ("claude_ai_Gmail", "label_thread", "Apply one or more labels to a Gmail thread", "email"),
    ("claude_ai_Gmail", "unlabel_thread", "Remove one or more labels from a Gmail thread", "email"),

    # Google Drive (claude.ai connector)
    ("claude_ai_Google_Drive", "search_files", "Search files in Google Drive by name or content", "files"),
    ("claude_ai_Google_Drive", "read_file_content", "Read the content of a Google Drive file (Docs, Sheets, text)", "files"),
    ("claude_ai_Google_Drive", "list_recent_files", "List recently modified files in Google Drive", "files"),
    ("claude_ai_Google_Drive", "create_file", "Create a new file in Google Drive", "files"),
    ("claude_ai_Google_Drive", "copy_file", "Copy an existing Google Drive file", "files"),
    ("claude_ai_Google_Drive", "get_file_metadata", "Get metadata (owner, dates, sharing) of a Google Drive file", "files"),
    ("claude_ai_Google_Drive", "download_file_content", "Download the raw content of a Google Drive file", "files"),

    # Todoist
    ("todoist", "add-tasks", "Create tasks in Todoist with content, priority (p1-p4), due dates, duration, and project assignment", "tasks"),
    ("todoist", "update-tasks", "Update existing Todoist tasks — priority, description, labels. Do NOT use for rescheduling.", "tasks"),
    ("todoist", "reschedule-tasks", "Move / reschedule a Todoist task to a new due date — move to next Friday, push to tomorrow, bump to Monday, postpone, defer (dời/đẩy lịch task sang ngày khác). Changes WHEN a task is due; preserves recurring schedules; YYYY-MM-DD.", "tasks"),
    ("todoist", "complete-tasks", "Mark Todoist tasks as completed", "tasks"),
    ("todoist", "find-tasks", "Search and filter Todoist tasks by project, label, priority, or text", "tasks"),
    ("todoist", "find-tasks-by-date", "Find Todoist tasks due on a specific date or date range", "tasks"),
    ("todoist", "find-completed-tasks", "List completed Todoist tasks by date range or project", "tasks"),
    ("todoist", "get-overview", "Get overview of Todoist workload and progress", "tasks"),

    # Readwise
    ("readwise", "readwise_search_highlights", "Search book and article highlights in Readwise by meaning or keywords", "reading"),
    ("readwise", "readwise_list_highlights", "List recent Readwise highlights with filtering", "reading"),
    ("readwise", "reader_search_documents", "Search saved articles and documents in Readwise Reader", "reading"),
    ("readwise", "reader_list_documents", "List documents in Readwise Reader by location (inbox, later, archive)", "reading"),
    ("readwise", "reader_get_document_details", "Get full details of a Readwise Reader document", "reading"),
    ("readwise", "reader_create_document", "Save a new document/URL to Readwise Reader", "reading"),
    ("readwise", "reader_get_document_highlights", "Get highlights from a specific Readwise Reader document", "reading"),
    ("readwise", "readwise_get_daily_review", "Get today's Readwise daily review highlights", "reading"),
    ("readwise", "reader_move_documents", "Move Readwise Reader documents between locations (inbox, later, shortlist, archive) — used by /inbox triage", "reading"),
    ("readwise", "reader_add_tags_to_document", "Add tags to a Readwise Reader document", "reading"),
    ("readwise", "reader_remove_tags_from_document", "Remove tags from a Readwise Reader document", "reading"),
    ("readwise", "reader_list_tags", "List all tags used in Readwise Reader", "reading"),
    ("readwise", "reader_bulk_edit_document_metadata", "Bulk edit metadata (location, tags) of multiple Readwise Reader documents", "reading"),
    ("readwise", "reader_export_documents", "Export Readwise Reader documents with content", "reading"),
    ("readwise", "reader_set_highlight_notes", "Set or update notes on a Readwise Reader highlight", "reading"),
    ("readwise", "readwise_create_highlights", "Create new highlights in Readwise manually", "reading"),
    ("readwise", "readwise_update_highlight", "Update an existing Readwise highlight's text, note, or tags", "reading"),

    # Context7 (claude.ai connector)
    ("claude_ai_Context7", "resolve-library-id", "Resolve a library name to its Context7 ID for documentation lookup", "docs"),
    ("claude_ai_Context7", "query-docs", "Query library documentation via Context7 for up-to-date code examples", "docs"),

    # haingt-brain (self-reference)
    ("haingt-brain", "brain_save", "Save a memory (decision, discovery, pattern, entity, preference) with semantic embedding", "memory"),
    ("haingt-brain", "brain_recall", "Search memories using hybrid semantic + keyword search", "memory"),
    ("haingt-brain", "brain_forget", "Delete a memory by ID. Full CRUD.", "memory"),
    ("haingt-brain", "brain_update", "Update a memory's content, tags, or metadata while preserving ID and access history", "memory"),
    ("haingt-brain", "brain_tools", "Semantic Toolbox — find the right tool/skill for a task by meaning", "memory"),
    ("haingt-brain", "brain_session", "Session lifecycle — start, save learnings, check status", "memory"),
    ("haingt-brain", "brain_graph", "Traverse knowledge graph from a memory entity", "memory"),

    # Civitai (project-scoped → home-server; image-gen model/prompt mining for Forge.
    # Names captured live 2026-06-13. Skipped get-by-ID/hash plumbing (get_model,
    # get_model_version[_mini|_by_hash|_by_hashes]), user-info (get_current_user),
    # the get_download_url sub-primitive, lookup/filter helpers (lookup_users,
    # get_creators, get_tags), and TRAIL/history bookkeeping (mark_as_used, mark_trail,
    # get_trail, get_trail_stats) — they dilute top-k. The /civitai-model skill wraps the workflow.)
    ("civitai", "search_models", "Search Civitai for AI image models — find a LoRA, checkpoint, ControlNet, or embedding by name / type / base-model (SDXL, Pony, Illustrious, NoobAI, Flux). Tìm model/LoRA trên Civitai.", "imagegen"),
    ("civitai", "browse_images", "Browse AI-generated images/videos on Civitai with their prompts + generation params — inspiration and prompt mining, filter by tag / base-model / NSFW level.", "imagegen"),
    ("civitai", "get_top_loras", "Get the most popular / trending LoRAs for a base model (SDXL, Pony, Illustrious, Flux).", "imagegen"),
    ("civitai", "get_top_checkpoints", "Get the most popular / trending checkpoint models for a base model — best SDXL, Pony, Flux, Illustrious checkpoints.", "imagegen"),
    ("civitai", "get_top_images", "Get top Civitai images/videos by reactions — best source of great prompts to copy, filter by tag / base-model / browsing-level.", "imagegen"),
    ("civitai", "get_image_generation_data", "Extract full generation parameters (prompt, negative, sampler, CFG, LoRA combos) from a model's top images — prompt mining for a specific model.", "imagegen"),
    ("civitai", "get_model_images", "Get example images for a specific model with full gen params (prompt, steps, CFG, seed, LoRAs) — learn how to use a model well.", "imagegen"),
    ("civitai", "get_download_info", "Get authenticated download URLs + ready-to-paste curl/PowerShell commands for a Civitai model — download a LoRA / checkpoint. Tải model về Forge.", "imagegen"),
    ("civitai", "check_permissions", "Check whether model versions are downloadable or early-access gated (membership / purchase) before attempting a download.", "imagegen"),
    ("civitai", "get_enums", "Get valid Civitai enum values — supported ModelType, BaseModel, ActiveBaseModel strings for filtering searches.", "imagegen"),

    # SillyTavern (project-scoped → home-server; manage ST chat-UI data live, no container
    # restart — ST hot-reloads on save. Names captured live 2026-06-13. All 8 are
    # task-discoverable, so the whole server surface is indexed.)
    ("st", "st_list_characters", "List all SillyTavern character cards (name, avatar, tags) — browse available RP characters.", "sillytavern"),
    ("st", "st_get_character", "Read a SillyTavern character card's full data — description, personality, scenario, first message.", "sillytavern"),
    ("st", "st_get_settings", "Read SillyTavern settings at a dotted path (SD image-gen config, persona descriptions, sampler, lorebook list) — path-based to avoid huge tree dumps.", "sillytavern"),
    ("st", "st_save_settings_path", "Surgically update one SillyTavern setting at a dotted path — ST hot-reloads, no container restart, no save race.", "sillytavern"),
    ("st", "st_save_settings", "Overwrite the full SillyTavern settings tree — prefer st_save_settings_path for surgical edits.", "sillytavern"),
    ("st", "st_get_worldinfo", "Read a SillyTavern World Info lorebook by name — entries + metadata.", "sillytavern"),
    ("st", "st_save_worldinfo", "Overwrite a SillyTavern World Info lorebook (full data dict) — read first to merge rather than blow away entries.", "sillytavern"),
    ("st", "st_get_recent_chat", "List recent chat sessions for a SillyTavern character (metadata: file, size, last message).", "sillytavern"),

    # Aseprite (project-scoped → chimera; the pixel-art ASSEMBLY + QA layer, driving Steam
    # Aseprite 1.3.17.2 fully headless via the diivi/aseprite-mcp 104-tool build. Captured
    # live 2026-06-13, REFRESHED 2026-06-18 after our group-support PRs merged upstream
    # (#18 group-aware find_layer + #19 add_group / add_layer group param). CURATED to the
    # task-discoverable jobs in art-pipeline.md §4.5 — the ~67 omitted tools are granular
    # siblings (no-suffix draw variants, per-cel/-frame/-slice/-tile getters+setters, region/
    # onion-skin/merge/flip/rotate primitives) folded into the descriptions below; reach for
    # them via §4.5 once in-flow. Standing law: layer GROUPS now supported on the CREATE/TARGET
    # path — draw/edit/create tools resolve a `group/child` layer path, add_group + add_layer's
    # group param create into groups (#18/#19); BUT enumerating readers (get_sprite_info,
    # audit_animation) still list only top-level layers — use export_layers / run_lua_script to
    # see inside groups. RGB masters only for palette/read ops, trust result-text not transport-ok.
    # NOT a generator — NINE/enemies stay on the SD pipeline; this is assembly/QA. Full verified
    # table + guardrails = §4.5.)
    ("aseprite", "create_canvas", "Create a new Aseprite sprite/canvas (always RGB) — scaffold a sprite at a given size. Silently overwrites an existing file; copy_sprite first. Tạo file sprite mới.", "pixelart"),
    ("aseprite", "add_layer", "Add a layer to an Aseprite sprite — optional group param nests it inside a named group (name or 'group/subgroup' path; #19). Create the group first with add_group. Thêm layer (vào group nếu cần).", "pixelart"),
    ("aseprite", "import_image_as_layer", "Import a PNG/image into an Aseprite sprite as a new layer at an exact offset — Stage-2 PNG → master import.", "pixelart"),
    ("aseprite", "copy_layers_between_sprites", "Copy named layers from one Aseprite sprite into another, pixel-exact — the PNG→master import (a PNG's single layer is named 'Layer'; no size guard, check dims first). Import ảnh SD vào master sprite.", "pixelart"),
    ("aseprite", "set_tag", "Create/update an animation tag — a named frame range + direction (forward/reverse/pingpong) on an Aseprite sprite. Build ALL frames before tagging (bounds are strict). Sibling: delete_tag.", "pixelart"),
    ("aseprite", "apply_dither_gradient", "Apply a dithered gradient in Aseprite — on-palette, normalize-safe shading. PREFER for on-palette work; sibling apply_dither_pattern for pattern fills (apply_gradient_rect is normalize-safe too since #24, just not palette-aware).", "pixelart"),
    ("aseprite", "draw_pixels", "Draw a batch of individual pixels in Aseprite from an {x,y,color} list — the freehand / ASCII-grid workflow (#RRGGBB or #RRGGBBAA per-pixel alpha since #24). Targeted geometric draws = the draw_*_at variants (line/rectangle/circle/ellipse/fill_area).", "pixelart"),
    ("aseprite", "remap_colors_in_cel_range", "Remap exact colors across an Aseprite layer/frame range via explicit mappings — the corruption value-band swap (bright→dark, §9.1). False-succeeds silently — readback-verify every call. Đổi màu corruption.", "pixelart"),
    ("aseprite", "generate_color_ramp", "Generate a hue-shifted dark→light shading ramp from a base color in Aseprite — color-blind value ramps (keep lightness_range ≤0.5 or the darkest step clamps to #000000). Returns a hex array.", "pixelart"),
    ("aseprite", "set_palette", "Set/replace an Aseprite sprite's color palette. Siblings: get_palette (read), apply_palette_preset + list_palette_presets (built-in presets).", "pixelart"),
    ("aseprite", "quantize_to_palette", "Snap every pixel of an Aseprite sprite to the nearest palette color (RGB distance) — machine palette enforcement (§9.1), run after set_palette/apply_palette_preset. RGB-only; verify unique_colors == palette size. Ép palette / quantize.", "pixelart"),
    ("aseprite", "get_color_stats", "Get color statistics of an Aseprite sprite — accurate unique-color count, sees inside groups (the palette-audit instrument). RGB-only. Đếm màu / audit palette.", "pixelart"),
    ("aseprite", "audit_animation", "Audit an Aseprite animation — per-layer/per-frame cel report for QA (audits TOP-LEVEL layers only — counts a group as one layer, skips cels nested inside it; populated JSON since PR#12).", "pixelart"),
    ("aseprite", "get_sprite_info", "Get Aseprite sprite metadata — size, layers (now recursed: every layer carries a parent, null at top level, since #22), frames, tags. The QA readback. Visible/composite pixel = get_composite_pixel.", "pixelart"),
    ("aseprite", "get_pixel_color", "Read the color of a single pixel in an Aseprite sprite — readback-verify after unchecked draws (pass an explicit layer_name; reads ONE cel). Bulk = get_pixels_rect; the VISIBLE composite of all layers = get_composite_pixel / get_composite_rect (#20).", "pixelart"),
    ("aseprite", "create_slice", "Create a named slice (a rectangular game-engine region / 9-patch / atlas frame) in an Aseprite sprite. Siblings: set_slice_center (9-patch), set_slice_pivot, list_slices (JSON-safe for any name since #21), delete_slice.", "pixelart"),
    ("aseprite", "create_tilemap_layer", "Create a tilemap layer with its own tileset in Aseprite — level/tileset authoring (tile index 0 = empty). Siblings: draw_on_tile, set_tiles, get_tile_at, get_tilemap_info.", "pixelart"),
    ("aseprite", "export_sprite", "Export an Aseprite sprite to PNG (multi-frame fans out to name1..N.png, digit-free basenames). Xuất PNG.", "pixelart"),
    ("aseprite", "export_layers", "Export each Aseprite layer as its own PNG — native --split-layers, the one export that PIERCES groups (incl. group children).", "pixelart"),
    ("aseprite", "export_spritesheet", "Export an Aseprite sprite as a packed spritesheet + JSON atlas (validates the tag). Xuất spritesheet.", "pixelart"),
    ("aseprite", "run_lua_script", "Run arbitrary Aseprite Lua in batch mode — the escape hatch for anything no tool covers (reproduces celdump / palette_audit). Does NOT auto-save (spr:saveAs required) and returns BLANK on error (use print() markers to verify).", "pixelart"),
    ("aseprite", "cvd_palette_audit", "Audit an Aseprite palette/ramp for colour-blind collisions — simulates protan/deuter/tritan (libDaltonLens, byte-for-byte == the AseCvdSim extension) and flags pairs distinct to normal vision but COLLAPSING for CVD viewers. The ~8% colour-blind accessibility gate the (normal-vision) dev can't self-check. Kiểm tra mù màu / CVD.", "pixelart"),
    ("aseprite", "value_contrast_check", "Check WCAG value-contrast between two corruption-stage ramps in Aseprite (assert ≥ min_ratio, default 3:1) — the corruption-stage readability gate (the value jump must read instantly + in grayscale). Sibling value_monotonic_check (ramp luminance strictly dark→light, the Tier-3 EXIT criterion). Kiểm tra tương phản value.", "pixelart"),
    ("aseprite", "kcentroid_downscale", "Content-aware downscale (kCentroid) of an image via Aseprite-MCP — dominant-colour-per-tile, keeps the hard pixel silhouette that naive nearest/lanczos blurs. The FAITHFUL many-colour Stage-2 AI→grid downscale (+ optional MAXCOVERAGE quantize); k-means AVERAGES per tile so it invents intermediate colours (unpredictable) — for the predictable value-first block-in use value_blockin_downscale (§3.6). Needs the numpy/pillow 'chimera' extra. Downscale ảnh AI thành pixel (giữ nhiều màu).", "pixelart"),
    ("aseprite", "value_blockin_downscale", "Predictable value-first downscale via Aseprite-MCP — grayscale → posterize to N levels → MODE downscale (most-frequent EXISTING value per tile), so output is GUARANTEED a subset of the N chosen values (0 invented colours; self-reports invented=0 + the K used). Method-of-record for the value-first hand-author path (§3.6): turns an AI render into a clean N-value silhouette + value block-in to refine by hand, COLOUR LAST. Distinct from kcentroid_downscale (k-means averages → invents colours, for a faithful many-colour downscale). levels=N (default 5), supersample=0=auto-K (working≈source, the orphan floor). Grayscale PNG out; needs the numpy/pillow 'chimera' extra. Downscale render thành block-in value sạch (đoán trước được) để pixel tay.", "pixelart"),
    ("aseprite", "extract_palette", "Extract an OPTIMAL palette from an Aseprite sprite via native ColorQuantization (true extraction, vs quantize_to_palette's nearest-snap) — returns the built palette and writes it to the sprite. Trích palette tối ưu từ art.", "pixelart"),
    ("aseprite", "apply_convolution", "Apply a native Aseprite convolution filter — blur / sharpen / edge / emboss (38 built-in matrices; list_convolution_matrices for the names). Engine-quality. Siblings (native app.command filters, optional region scope): outline_native, adjust_hsl_native, adjust_brightness_contrast, invert_colors.", "pixelart"),
]

# ── Plugin-bundled MCP Tools ─────────────────────────────────────────────────
# MCP servers that ship INSIDE a marketplace plugin (the plugin's own .mcp.json),
# NOT in ~/.claude.json or a project .mcp.json — so _mcp_server_scopes() cannot see them.
# Claude Code registers them as `plugin_<pluginName>_<serverName>` (the godot-dev plugin's
# "godot" server → plugin_godot-dev_godot). Curated like MCP_TOOLS; scope is resolved by
# discover_plugin_mcp_scopes() from installed_plugins.json + per-project enabledPlugins, so
# a plugin enabled in N projects yields one tool entry PER project (the single-scope
# _mcp_server_scopes() dict can't express multi-project availability). Captured live
# 2026-06-13 from a chimera session. Each entry: (plugin_name, server, tool, desc, category).
# godot-mcp = Coding-Solo @coding-solo/godot-mcp; skipped UID/meta/3D plumbing (get_uid,
# update_project_uids, get_godot_version, list_projects, export_mesh_library). Usage law +
# probe caveats = tech.md "Godot MCP" (e.g. NEVER --headless --write-movie: segfault).
PLUGIN_MCP_TOOLS = [
    ("godot-dev", "godot", "create_scene", "Create a new Godot scene (.tscn) with a chosen root node type (Node2D/Node3D/Control) — scaffold a scene file.", "godot"),
    ("godot-dev", "godot", "add_node", "Add a node to an existing Godot scene (e.g. Sprite2D, CollisionShape2D, Area2D, AnimationPlayer) under a parent path, with optional properties.", "godot"),
    ("godot-dev", "godot", "save_scene", "Save changes to a Godot scene file (optionally to a new path to create a variant).", "godot"),
    ("godot-dev", "godot", "load_sprite", "Load a texture/image into a Sprite2D node in a Godot scene — set the sprite's texture.", "godot"),
    ("godot-dev", "godot", "run_project", "Run a Godot project (optionally a specific scene) and capture its output — launch the game to test it. Chạy thử game Godot.", "godot"),
    ("godot-dev", "godot", "stop_project", "Stop the currently running Godot project.", "godot"),
    ("godot-dev", "godot", "get_debug_output", "Get the current Godot debug output and errors from the running project — read runtime logs / stack traces.", "godot"),
    ("godot-dev", "godot", "launch_editor", "Launch the Godot editor GUI for a project.", "godot"),
    ("godot-dev", "godot", "get_project_info", "Retrieve metadata about a Godot project — engine version, settings, structure.", "godot"),
]

# ── CLI Tools ──────────────────────────────────────────────────────────────
# Manually curated. Each entry: (command, description, category)

CLI_TOOLS = [
    ("chub search", "Search curated LLM-optimized docs and skills for libraries/frameworks. Usage: chub search [query] --json", "docs"),
    ("chub get", "Fetch curated documentation by ID with language variant. Usage: chub get <id> --lang py|js", "docs"),
    ("gh pr create", "Open a GitHub PR from the terminal — drives the stacked-PR workflow on the aseprite-mcp fork. Usage: gh pr create --base main --head <branch> --title .. --body ..", "development"),
    ("gh pr view", "View a GitHub PR's status, CI checks, and review comments from the CLI — confirm a PR merged or see what's failing. Usage: gh pr view <n> --comments ; gh pr checks <n>", "development"),
    ("gh run watch", "Watch or inspect GitHub Actions CI runs from the terminal — follow a build, see why it failed. Usage: gh run watch ; gh run view <id> --log-failed", "development"),
    ("gh issue create", "File or list GitHub issues from the CLI — upstream bug reports and feature filings. Usage: gh issue create --repo owner/repo --title .. ; gh issue list", "development"),
    ("yt-dlp", "Download video/audio + metadata from YouTube and 1000+ sites — pull reference/source footage for Bookie video. Usage: yt-dlp -f best <url> ; -x --audio-format mp3 for audio. Tải video nguồn.", "content"),
    ("rg", "ripgrep — fast recursive code/content search across a tree (respects .gitignore). Daily driver for Godot/GDScript, the Calibre library, and docs. Usage: rg -n 'pattern' path ; -t gd ; -g '!dir'. Tìm trong code/text.", "development"),
    ("jq", "Slice / filter / reshape JSON from the CLI — MCP payloads, Aseprite atlas exports, Civitai gen-params, brain.db json_extract output. Usage: jq '.key[] | select(.x)' file.json. Xử lý JSON.", "development"),
]


# ── Native (binary-bundled) Skills ──────────────────────────────────────────
# Built into the Claude Code binary — NO filesystem SKILL.md, so they can't be
# auto-discovered like user/project/plugin skills. Manually curated here, same as
# MCP_TOOLS/CLI_TOOLS. Indexed with protocol="native-skill" so the filesystem
# drift check (which only validates protocol="skill") never flags them as stale.
# Re-verify this list against the available-skills list when the CC binary updates.
# Each entry: (name, description, category)

NATIVE_SKILLS = [
    ("deep-research", "Research any topic on the web — look into / investigate / find out the latest on X, market & competitor research; deep multi-source fact-checked report (fan-out web search, fetch sources, adversarial 3-vote verify, cited synthesis). VN: nghiên cứu, tìm hiểu sâu, điều tra, khảo sát.", "research"),
    ("code-review", "Review the current git diff/branch for correctness bugs and reuse/simplification/efficiency cleanups at a chosen effort level (low to ultra). Can post inline PR comments or apply fixes.", "development"),
    ("simplify", "Review changed code for reuse, simplification, efficiency, and altitude cleanups, then apply the fixes. Quality cleanup only — does not hunt bugs (use /code-review for that).", "development"),
    ("security-review", "Security review of the pending changes on the current branch — find vulnerabilities, injection, auth/secret exposure in the diff.", "development"),
    ("review", "Review a pull request — read the PR diff and leave structured review feedback.", "development"),
    ("verify", "Verify a code change actually works by running the app and observing behavior — confirm a fix/PR/feature works, validate local changes before pushing.", "development"),
    ("run", "Launch and drive this project's app to see a change working — run/start/screenshot the app, confirm a change works in the real app (not just tests).", "development"),
    ("init", "Initialize a new CLAUDE.md file documenting the codebase for Claude Code.", "development"),
    ("claude-api", "Reference for the Claude API / Anthropic SDK — model ids, pricing, params, streaming, tool use, MCP, agents, prompt caching, token counting, model migration. For building on Claude/Anthropic.", "reference"),
    ("update-config", "Configure the Claude Code harness via settings.json — hooks for automated behaviors (when X do Y), permissions/allowlists, env vars, hook troubleshooting.", "harness"),
    ("keybindings-help", "Customize Claude Code keyboard shortcuts — rebind keys, add chord bindings, change the submit key, edit ~/.claude/keybindings.json.", "harness"),
    ("fewer-permission-prompts", "Scan transcripts for common read-only Bash/MCP calls and add a prioritized allowlist to project settings.json to reduce permission prompts.", "harness"),
    ("loop", "Run a prompt or slash command on a recurring interval (e.g. /loop 5m /foo) or self-paced — poll status or repeat a task on a schedule.", "harness"),
    ("schedule", "Create, update, list, or run scheduled cloud agents (routines) on a cron schedule — automated recurring Claude Code tasks, or a one-time scheduled run.", "harness"),
]


# ── Skill Auto-Discovery ──────────────────────────────────────────────────

GLOBAL_SKILLS_DIR = Path.home() / ".claude" / "skills"
PROJECTS_DIR = Path.home() / "Projects"
PLUGINS_DIR = Path.home() / "Projects" / "agent" / "plugins"

# Skip patterns
SKIP_DIRS = {"skill-snapshot", "workspace"}


def _parse_skill(path: Path) -> dict | None:
    """Parse a SKILL.md file. Returns {name, description, body_context} or None.

    description: from frontmatter (trimmed label, used for display)
    body_context: first ~300 chars of body content (enriches brain index for search)
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None

    # Match YAML frontmatter between ---
    match = re.match(r"^---\n(.*?)\n---\s*\n?(.*)", text, re.DOTALL)
    if not match:
        return None

    frontmatter = match.group(1)
    body = match.group(2).strip()
    result = {}

    # Extract name
    name_match = re.search(r'^name:\s*(.+)$', frontmatter, re.MULTILINE)
    if name_match:
        result["name"] = name_match.group(1).strip().strip('"\'')

    # Extract description (single-line or multi-line >- / >)
    desc_match = re.search(r'^description:\s*[>|]-?\s*\n((?:\s+.+\n?)+)', frontmatter, re.MULTILINE)
    if desc_match:
        # Multi-line: join folded lines
        lines = desc_match.group(1).strip().split("\n")
        result["description"] = " ".join(line.strip() for line in lines)
    else:
        # Single-line
        desc_match = re.search(r'^description:\s*(.+)$', frontmatter, re.MULTILINE)
        if desc_match:
            result["description"] = desc_match.group(1).strip().strip('"\'')

    # Extract body context: first ~300 chars after frontmatter for richer search
    # signal. Word-boundary cut — mid-word truncation shipped broken sentences
    # into every injection of the tool (audit 2026-06-12).
    if body:
        # Strip markdown headers for cleaner text
        body_clean = re.sub(r'^#+\s+', '', body, flags=re.MULTILINE)
        snippet = body_clean[:300].strip()
        if len(body_clean) > 300:
            cut = snippet.rfind(" ")
            if cut > 150:
                snippet = snippet[:cut]
        result["body_context"] = snippet

    if "name" in result and "description" in result:
        return result
    return None


def _infer_category(description: str) -> str:
    """Infer category from skill description using keyword matching.

    Order matters: more specific categories first, broader ones last.
    """
    desc_lower = description.lower()

    # Most specific first → broadest last
    categories = [
        # Domain-specific (narrow, unambiguous keywords)
        ("game-dev", ["godot", "gdd", "gut test", "gdscript", "gdformat", "gdlint"]),
        ("infra", ["podman", "setup.sh", "prerequisite", "diagnostics", "media stack"]),
        ("finance", ["financial", "budget", "projection", "runway"]),
        ("freelance", ["upwork", "proposal", "gig"]),
        ("triage", ["inbox", "triage"]),
        ("coaching", ["accountability", "milestone", "mentor"]),
        ("self", ["reflect", "profile dimension", "staleness", "satisfaction"]),
        ("learning", ["anki", "flashcard", "vocab", "learning path"]),
        ("scheduling", ["schedule", "quest", "calendar", "optimize day"]),
        ("optimization", ["token", "consumption", "context waste"]),
        # Content creation (before creative — video/storyboard/prompts are content pipeline)
        ("content", ["video", "storyboard", "tts", "book video", "youtube", "facebook",
                      "metadata for", "narrative arc", "pacing", "per-scene", "image prompts"]),
        ("creative", ["generate image", "concept art"]),
        ("library", ["calibre", "owned book", "owned-library", "my shelf", "book library", "titles to acquire"]),
        ("research", ["research", "decision intelligence"]),
        # Development (ship, fix, commit, scaffold)
        ("development", ["github issue", "commit", "open pr", "ship change", "fix.*issue",
                         "ship", "lint.*test.*review", "sub-project", "scaffold"]),
        ("knowledge", ["obsidian", "vault note", "catalog insight", "sync.*compact"]),
        # Fallback for setup/config skills
        ("infra", ["setup", "dry-run", "prerequisite"]),
    ]
    for category, keywords in categories:
        if any(re.search(kw, desc_lower) for kw in keywords):
            return category
    return "general"


def discover_skills() -> list[dict]:
    """Auto-discover skills from filesystem.

    Returns: [{"name", "description", "body_context", "category", "project"}, ...]
    Scans:
      ~/.claude/skills/*/SKILL.md → global (project=None)
      ~/Projects/*/.claude/skills/*/SKILL.md → project-scoped
    """
    skills = []

    # Global skills
    if GLOBAL_SKILLS_DIR.exists():
        for skill_dir in sorted(GLOBAL_SKILLS_DIR.iterdir()):
            if not skill_dir.is_dir():
                continue
            if any(skip in skill_dir.name for skip in SKIP_DIRS):
                continue
            skill_file = skill_dir / "SKILL.md"
            if not skill_file.exists():
                continue
            parsed = _parse_skill(skill_file)
            if parsed:
                desc = parsed["description"]
                body = parsed.get("body_context", "")
                category = _infer_category(desc)
                skills.append({
                    "name": parsed["name"],
                    "description": desc,
                    "body_context": body,
                    "category": category,
                    "project": None,
                })

    # Project skills
    if PROJECTS_DIR.exists():
        for project_dir in sorted(PROJECTS_DIR.iterdir()):
            if not project_dir.is_dir():
                continue
            skills_dir = project_dir / ".claude" / "skills"
            if not skills_dir.exists():
                continue
            project_name = project_dir.name
            for skill_dir in sorted(skills_dir.iterdir()):
                if not skill_dir.is_dir():
                    continue
                if any(skip in skill_dir.name for skip in SKIP_DIRS):
                    continue
                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue
                parsed = _parse_skill(skill_file)
                if parsed:
                    desc = parsed["description"]
                    body = parsed.get("body_context", "")
                    category = _infer_category(desc)
                    skills.append({
                        "name": parsed["name"],
                        "description": desc,
                        "body_context": body,
                        "category": category,
                        "project": project_name,
                    })

    return skills


def _global_enabled_plugins() -> dict:
    """Read global enabledPlugins from ~/.claude/settings.json (governs user-scope plugins)."""
    p = Path.home() / ".claude" / "settings.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("enabledPlugins", {})
    except (OSError, json.JSONDecodeError):
        return {}


def _project_enables_plugin(project_path: str, plugin_key: str) -> bool:
    """Whether a project's own settings.json enables this plugin (governs project-scope plugins)."""
    p = Path(project_path) / ".claude" / "settings.json"
    try:
        return bool(json.loads(p.read_text(encoding="utf-8")).get("enabledPlugins", {}).get(plugin_key, False))
    except (OSError, json.JSONDecodeError):
        return False


def discover_plugin_skills() -> list[dict]:
    """Discover skills from INSTALLED + ENABLED marketplace plugins — the authoritative
    "what Claude actually loads" view, read from installed_plugins.json + enabledPlugins.

    Scope handling, so brain_tools never suggests a plugin not available in a given project:
      - user-scope plugin, globally enabled            → global skill (project=None, everywhere)
      - project-scope plugin, enabled in that project  → skill scoped to that project only
    Uninstalled plugins (e.g. mcp-server-dev) and superseded cache versions are absent from
    installed_plugins.json, so they drop out for free. This replaces the old dev-location scan
    (~/Projects/agent/plugins): the cache at installPath is what Claude loads; the dev tree is
    just marketplace source.
    """
    installed_file = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    if not installed_file.exists():
        return []
    try:
        installed = json.loads(installed_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []

    global_enabled = _global_enabled_plugins()
    out: list[dict] = []
    seen: set[tuple[str, str | None]] = set()

    for plugin_key, records in installed.get("plugins", {}).items():
        plugin_name = plugin_key.split("@", 1)[0]
        for rec in records:
            scope = rec.get("scope")
            skills_dir = Path(rec.get("installPath", "")) / "skills"
            if not skills_dir.exists():
                continue
            # Resolve which project(s) this install serves + whether it's enabled there.
            if scope == "user":
                if not global_enabled.get(plugin_key, False):
                    continue
                projects: list[str | None] = [None]
            elif scope == "project":
                pp = rec.get("projectPath")
                if not pp or not _project_enables_plugin(pp, plugin_key):
                    continue
                projects = [Path(pp).name]
            else:
                continue

            for skill_dir in sorted(skills_dir.iterdir()):
                if not skill_dir.is_dir() or any(skip in skill_dir.name for skip in SKIP_DIRS):
                    continue
                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue
                parsed = _parse_skill(skill_file)
                if not parsed:
                    continue
                desc = parsed["description"]
                body = parsed.get("body_context", "")
                category = _infer_category(desc)
                for proj in projects:
                    key = (parsed["name"], proj)
                    if key in seen:
                        continue
                    seen.add(key)
                    out.append({
                        "name": parsed["name"],
                        "description": desc,
                        "body_context": body,
                        "category": category,
                        "project": proj,
                        "plugin": plugin_name,
                    })
    return out


def discover_plugin_mcp_scopes() -> dict:
    """Map a plugin-bundled MCP server (composed name `plugin_<plugin>_<server>`) → the list
    of project scopes where it's available ([None] = global/user-scope plugin).

    The companion to discover_plugin_skills for the MCP side: _mcp_server_scopes() only reads
    ~/.claude.json + ~/Projects/<p>/.mcp.json, so a server shipped in a plugin's OWN .mcp.json
    is invisible to it. Reads installed_plugins.json, opens each install's .mcp.json for its
    server names, and gates by scope + enablement exactly like discover_plugin_skills. Returns
    a LIST of scopes per server (not a single one) because a plugin enabled in N projects makes
    its server available in all N — the indexer then saves one tool entry per project.
    """
    installed_file = Path.home() / ".claude" / "plugins" / "installed_plugins.json"
    if not installed_file.exists():
        return {}
    try:
        installed = json.loads(installed_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}

    global_enabled = _global_enabled_plugins()
    out: dict[str, list[str | None]] = {}

    for plugin_key, records in installed.get("plugins", {}).items():
        plugin_name = plugin_key.split("@", 1)[0]
        for rec in records:
            scope = rec.get("scope")
            mcp_file = Path(rec.get("installPath", "")) / ".mcp.json"
            if not mcp_file.exists():
                continue
            try:
                servers = json.loads(mcp_file.read_text(encoding="utf-8")).get("mcpServers", {})
            except (OSError, json.JSONDecodeError):
                continue
            if not servers:
                continue
            # Resolve which project this install serves + whether the plugin is enabled there.
            if scope == "user":
                if not global_enabled.get(plugin_key, False):
                    continue
                proj: str | None = None
            elif scope == "project":
                pp = rec.get("projectPath")
                if not pp or not _project_enables_plugin(pp, plugin_key):
                    continue
                proj = Path(pp).name
            else:
                continue
            for server in servers:
                composed = f"plugin_{plugin_name}_{server}"
                bucket = out.setdefault(composed, [])
                if proj not in bucket:
                    bucket.append(proj)
    return out


# ── MCP Server Scoping ─────────────────────────────────────────────────────

def _mcp_server_scopes() -> dict:
    """Map each MCP server name → its scope: None (global/user) or a project name.

    A project-scoped server's tools must only be suggested in that project — e.g. `readwise`
    lives in digital-identity/.mcp.json, so its tools should NOT surface in chimera/Bookie.
      - Global: user-level servers in ~/.claude.json top-level mcpServers (todoist, haingt-brain),
        plus claude.ai account connectors (claude_ai_*), which aren't in any file config.
      - Project: servers declared in ~/Projects/<p>/.mcp.json or ~/.claude.json projects[<p>].mcpServers.
    User-level scope wins over a project declaration (setdefault preserves the global mark).
    """
    scopes: dict = {}
    home = Path.home()
    cj = {}
    try:
        cj = json.loads((home / ".claude.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cj = {}
    # User-level (global) servers
    for srv in cj.get("mcpServers", {}):
        scopes[srv] = None
    # Project-scoped servers declared inline in ~/.claude.json
    for proj_path, cfg in cj.get("projects", {}).items():
        proj = Path(proj_path).name
        for srv in (cfg.get("mcpServers", {}) or {}):
            scopes.setdefault(srv, proj)
    # Project-scoped servers from each ~/Projects/<p>/.mcp.json
    projects_dir = home / "Projects"
    if projects_dir.exists():
        for proj_dir in projects_dir.iterdir():
            if not proj_dir.is_dir():
                continue
            mcp_file = proj_dir / ".mcp.json"
            if not mcp_file.exists():
                continue
            try:
                servers = json.loads(mcp_file.read_text(encoding="utf-8")).get("mcpServers", {})
            except (OSError, json.JSONDecodeError):
                continue
            for srv in (servers or {}):
                scopes.setdefault(srv, proj_dir.name)
    return scopes


# ── Drift Validation ──────────────────────────────────────────────────────

def validate_tool_index(conn) -> dict | None:
    """Compare indexed skills vs filesystem. Returns drift report or None if synced."""
    rows = conn.execute(
        "SELECT json_extract(metadata, '$.name') as name, project FROM memories "
        "WHERE type='tool' AND json_extract(metadata, '$.protocol')='skill'"
    ).fetchall()
    indexed = {(row["name"], row["project"]) for row in rows if row["name"]}

    discovered = {(s["name"], s["project"]) for s in discover_skills()}

    missing = {f"{n} [{p or 'global'}]" for n, p in (discovered - indexed)}
    stale = {f"{n} [{p or 'global'}]" for n, p in (indexed - discovered)}

    if missing or stale:
        return {
            "missing": sorted(missing),
            "stale": sorted(stale),
            "indexed_count": len(indexed),
            "filesystem_count": len(discovered),
        }
    return None


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    conn = connect()
    init_schema(conn)

    # Atomic-ish rebuild: snapshot the OLD tool entries but DON'T delete them yet. The full new
    # set is built first; every brain_save makes a fresh random-uuid row, so new ids can never
    # collide with this snapshot. The snapshot is pruned only at the very end. During the rebuild
    # a reader sees old+new — full coverage, at worst a transient duplicate — never a half-empty
    # toolbox. Also interruption-safe: if the run dies mid-build, the old set stays intact.
    old_tool_ids = [row["id"] for row in
                    conn.execute("SELECT id FROM memories WHERE type = 'tool'").fetchall()]

    # Index MCP tools — scoped by their server's config (global vs project), so a
    # project-scoped server's tools (e.g. readwise → digital-identity) are never
    # suggested in projects where that server isn't configured.
    server_scopes = _mcp_server_scopes()
    print(f"\nIndexing {len(MCP_TOOLS)} MCP tools...")
    for mcp_server, tool_name, description, category in MCP_TOOLS:
        proj = server_scopes.get(mcp_server)  # None → global
        content = f"{tool_name}: {description}"
        brain_save(
            conn, content, "tool",
            tags=[mcp_server, tool_name, category],
            project=proj,
            metadata={
                "protocol": "mcp",
                "server": mcp_server,
                "name": tool_name,
                "category": category,
                "scope": proj or "global",
            },
        )
        print(f"  + {mcp_server}/{tool_name}" + (f" [{proj}]" if proj else ""))

    # Index plugin-bundled MCP tools — servers shipped inside a marketplace plugin's own
    # .mcp.json (invisible to _mcp_server_scopes()). Scope comes from the plugin's install
    # records; a server enabled in N projects is saved once per project so brain_tools never
    # suggests it where the plugin isn't enabled.
    plugin_mcp_scopes = discover_plugin_mcp_scopes()
    plugin_mcp_count = 0
    print(f"\nIndexing plugin-bundled MCP tools ({len(PLUGIN_MCP_TOOLS)} curated)...")
    for plugin_name, server, tool_name, description, category in PLUGIN_MCP_TOOLS:
        composed = f"plugin_{plugin_name}_{server}"
        projects = plugin_mcp_scopes.get(composed)
        if not projects:
            print(f"  ! skip {composed}/{tool_name} — plugin not installed/enabled anywhere")
            continue
        content = f"{tool_name}: {description}"
        for proj in projects:
            brain_save(
                conn, content, "tool",
                tags=[composed, tool_name, category],
                project=proj,
                metadata={
                    "protocol": "mcp",
                    "server": composed,
                    "name": tool_name,
                    "category": category,
                    "scope": proj or "global",
                    "plugin": plugin_name,
                },
            )
            plugin_mcp_count += 1
            print(f"  + {composed}/{tool_name}" + (f" [{proj}]" if proj else " [global]"))

    # Auto-discover and index skills
    skills = discover_skills()
    global_skills = [s for s in skills if s["project"] is None]
    project_skills = [s for s in skills if s["project"] is not None]

    print(f"\nDiscovered {len(skills)} skills ({len(global_skills)} global, {len(project_skills)} project)...")

    for skill in skills:
        name = skill["name"]
        project = skill["project"]
        category = skill["category"]
        scope = f"[{project}]" if project else "[global]"

        # Enriched content: description + body context for better search
        content = f"/{name}: {skill['description']}"
        if skill.get("body_context"):
            content += f" — {skill['body_context']}"

        brain_save(
            conn, content, "tool",
            tags=["skill", name, category],
            project=project,
            metadata={
                "protocol": "skill",
                "name": name,
                "category": category,
            },
        )
        print(f"  + /{name} {scope} ({category})")

    # Index native (binary-bundled) skills — curated, not filesystem-discoverable
    print(f"\nIndexing {len(NATIVE_SKILLS)} native skills...")
    for name, description, category in NATIVE_SKILLS:
        brain_save(
            conn, f"/{name}: {description}", "tool",
            tags=["skill", "native", name, category],
            metadata={
                "protocol": "native-skill",
                "name": name,
                "category": category,
            },
        )
        print(f"  + /{name} [native] ({category})")

    # Index installed + enabled plugin skills (authoritative from installed_plugins.json).
    # protocol="plugin-skill" keeps them out of the filesystem drift check, which only
    # validates protocol="skill" (the standard user/project dirs).
    plugin_skills = discover_plugin_skills()
    print(f"\nIndexing {len(plugin_skills)} plugin skills...")
    for skill in plugin_skills:
        name = skill["name"]
        project = skill["project"]
        category = skill["category"]
        content = f"/{name}: {skill['description']}"
        if skill.get("body_context"):
            content += f" — {skill['body_context']}"
        brain_save(
            conn, content, "tool",
            tags=["skill", "plugin", skill.get("plugin", ""), name, category],
            project=project,
            metadata={
                "protocol": "plugin-skill",
                "name": name,
                "category": category,
                "plugin": skill.get("plugin", ""),
            },
        )
        scope = f"[{project}]" if project else "[global]"
        print(f"  + /{name} {scope} (plugin:{skill.get('plugin', '')}, {category})")

    # Index CLI tools
    print(f"\nIndexing {len(CLI_TOOLS)} CLI tools...")
    for command, description, category in CLI_TOOLS:
        content = f"{command}: {description}"
        brain_save(
            conn, content, "tool",
            tags=["cli", command.split()[0], category],
            metadata={
                "protocol": "cli",
                "command": command,
                "name": command,
                "category": category,
            },
        )
        print(f"  + {command}")

    # Prune: the full new set is built, so delete the snapshotted old entries now. Up to this
    # point readers saw old+new (full coverage); after it, only the fresh set remains.
    # brain_forget also clears each entry's vector + FTS rows.
    if old_tool_ids:
        print(f"\nPruning {len(old_tool_ids)} superseded tool entries...")
        for oid in old_tool_ids:
            brain_forget(conn, oid)

    total = (len(MCP_TOOLS) + plugin_mcp_count + len(skills) + len(NATIVE_SKILLS)
             + len(plugin_skills) + len(CLI_TOOLS))
    print(f"\nDone! Indexed {total} capabilities into Semantic Toolbox.")
    print(f"  MCP tools: {len(MCP_TOOLS)}")
    print(f"  Plugin-bundled MCP tools: {plugin_mcp_count}")
    print(f"  Skills: {len(skills)} ({len(global_skills)} global + {len(project_skills)} project)")
    print(f"  Native skills: {len(NATIVE_SKILLS)}")
    print(f"  Plugin skills: {len(plugin_skills)} ({sum(1 for s in plugin_skills if s['project'] is None)} global + {sum(1 for s in plugin_skills if s['project'])} project)")
    print(f"  CLI tools: {len(CLI_TOOLS)}")

    # Project breakdown
    projects = {}
    for s in project_skills:
        proj = s["project"]
        projects[proj] = projects.get(proj, 0) + 1
    if projects:
        print("\n  Project skills breakdown:")
        for proj, count in sorted(projects.items()):
            print(f"    {proj}: {count}")

    # Quick verification
    from haingt_brain.tools.toolbox import brain_tools
    print("\n=== Verification ===")
    tests = [
        ("find free time on calendar", None),
        ("create a task", None),
        ("write video script", "Bookie"),
        ("create godot scene", "chimera"),
        ("check financial health", "digital-identity"),
        ("find docs for fastapi", None),
        ("review a pull request", None),
        ("schedule a recurring cloud agent", None),
        ("what books do I own about pixel art", None),
        ("create a new skill from scratch and run evals", None),
        ("debug a gdscript null-reference error in godot", "chimera"),
        ("create a new godot scene with a Node2D root", "chimera"),
        ("quantize a sprite to its palette in aseprite", "chimera"),
        ("downscale a render into a predictable value block-in for hand-pixeling", "chimera"),
    ]
    for query, project in tests:
        results = brain_tools(conn, query, k=1, project=project)
        if results:
            r = results[0]
            name = r.get("name", "?")
            proj = r.get("project", "global")
            print(f'  "{query}" (project={project}) → {name} [{proj}]')
        else:
            print(f'  "{query}" (project={project}) → NO MATCH')

    # Cross-project scope checks — a scoped capability must surface ONLY where available.
    print("\n=== Cross-project scope (no leaks) ===")
    scope_cases = [
        # (query, project, substring-expected-in-top3, present_expected)
        ("debug a gdscript error and inspect the godot scene tree", "chimera", "godot", True),
        ("debug a gdscript error and inspect the godot scene tree", "IronCradle", "godot", True),
        ("debug a gdscript error and inspect the godot scene tree", "digital-identity", "godot", False),
        ("save this article to my reading list and tag it", "digital-identity", "reader", True),
        ("save this article to my reading list and tag it", "chimera", "reader", False),
        ("save this article to my reading list and tag it", "Bookie", "reader", False),
        # plugin-bundled godot MCP tools — chimera+IronCradle only (godot-dev plugin scope)
        ("create a new godot scene and add a sprite node", "chimera", "create_scene", True),
        ("create a new godot scene and add a sprite node", "IronCradle", "create_scene", True),
        ("create a new godot scene and add a sprite node", "digital-identity", "create_scene", False),
        ("create a new godot scene and add a sprite node", "Bookie", "create_scene", False),
        # aseprite MCP tools — chimera only
        ("quantize a sprite to its palette and audit colors", "chimera", "quantize", True),
        ("quantize a sprite to its palette and audit colors", "IronCradle", "quantize", False),
        ("quantize a sprite to its palette and audit colors", "digital-identity", "quantize", False),
    ]
    scope_ok = True
    for query, proj, needle, expect in scope_cases:
        names = [r.get("name", "?") for r in brain_tools(conn, query, k=3, project=proj)]
        present = any(needle in n for n in names)
        ok = (present == expect)
        scope_ok = scope_ok and ok
        print(f'  {"OK  " if ok else "LEAK"} [{proj}] needle="{needle}" present={present} (expect {expect}) — top3={names}')
    print(f'  -> cross-project scope {"CLEAN" if scope_ok else "BROKEN — fix before shipping"}')

    # Drift check
    drift = validate_tool_index(conn)
    if drift:
        print(f"\n⚠ Tool index drift detected: {drift}")
    else:
        print("\n✓ Tool index in sync with filesystem")


if __name__ == "__main__":
    main()
