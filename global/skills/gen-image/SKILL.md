---
name: gen-image
disable-model-invocation: false
description: "Generate images via Gemini API from text prompts"
argument-hint: "<prompt-text-or-file-path> [--aspect 16:9] [--size 1K] [--model MODEL] [--output path] [--output-dir dir] [--prefix text] [--force]"
---

# Gen Image

Generate images via Gemini API. Single prompt or batch file.

## Script Location

```
SKILL_SCRIPT="$SKILL_DIR/scripts/gemini-gen-image.sh"
```

## Workflow

### 1. Parse Arguments

`$ARGUMENTS` can be:
- **Inline prompt**: plain text describing the image to generate
- **File path**: path to a batch prompt file (detect by checking if it's a valid file path ending in `.txt` or `.md`)
- **Empty**: ask what to generate

If arguments contain flags, extract them and pass through to the script.
Supported flags: --aspect, --size, --output, --output-dir, --model, --prefix, --force

### 2. Resolve Output

- If `--output` provided: use as-is
- If not provided and single mode: ask where to save, or suggest `/tmp/gen-image-<timestamp>.png`
- If batch mode with `--file`: use `--output-dir` (default: same directory as the prompt file)

### 3. Infer Defaults (for flags not explicitly provided)

**Aspect ratio:**
- Video scenes → `16:9`
- Social media / square → `1:1`
- Portrait → `9:16`
- Default → `16:9`

**Size:**
- Flashcard / Anki / thumbnail / icon → `512`
- Web / social media / general → `1K`
- Print / high-res / wallpaper → `2K`
- Default → `1K`

**Model:** Leave unset (script default: gemini-3.1-flash-image-preview) unless user specifies.

### 4. Execute

Run the bundled script via Bash:

```bash
# Single mode — pass all provided flags
"$SKILL_DIR/scripts/gemini-gen-image.sh" \
  --prompt "THE PROMPT" \
  --output "/path/to/output.png" \
  --aspect "$ASPECT" \
  --size "$SIZE" \
  $EXTRA_FLAGS
```

Or for batch:

```bash
# Batch mode — pass all provided flags
"$SKILL_DIR/scripts/gemini-gen-image.sh" \
  --file "/path/to/prompts.txt" \
  --output-dir "/path/to/dir/" \
  --aspect "$ASPECT" \
  --size "$SIZE" \
  $EXTRA_FLAGS
```

Where `$EXTRA_FLAGS` includes any of: `--model`, `--prefix`, `--force` if provided by the user.

### 5. Display Result

After successful generation:
1. Use the **Read** tool to display the generated image (Claude Code is multimodal — it can view PNG files)
2. Report: file path, file size

For batch: show summary (generated/skipped/failed counts), don't display all images individually unless asked.

### 6. Error Handling

- If GEMINI_API_KEY is missing: tell user to set it in `.env` or `~/.config/gemini/.env`
- If safety filter blocks: report the block reason, suggest rephrasing the prompt
- If retries exhausted: report failure, suggest checking the prompt or trying a different model

## Models

Known working Gemini image models (user can override via `--model`):
- `gemini-3.1-flash-image-preview` — default, good quality, proven in production
- `gemini-2.0-flash-preview-image-generation` — older variant (may be deprecated)
- `gemini-2.5-flash-preview-04-17` — newer variant

## Batch File Format

```
01 | prompt text for first image
02 | prompt text for second image
```

Lines starting with `#` are comments. Empty lines are skipped.
