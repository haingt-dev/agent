---
name: yt-fetch
description: "Fetch a YouTube video as readable markdown (title, channel, description, clean transcript). WebFetch can't read YouTube — this wraps a tested yt-dlp pipeline."
argument-hint: "<youtube-url> [output-dir]"
allowed-tools: Bash, Read
---

# yt-fetch — make a YouTube video readable

*Reach for this whenever you need to **read / study / summarize / quote a YouTube video** and WebFetch returns nothing — YouTube blocks AI fetch. Produces a clean transcript + metadata as markdown.*

WebFetch can't read YouTube. This runs a tested `yt-dlp` wrapper that pulls the video's captions + metadata (no video download) and cleans the auto-caption "rolling window" duplication into plain text.

## Use

```
scripts/yt-fetch.sh <youtube-url> [output-dir]
```

It prints the path to a single `<video-id>.md` (default dir: cwd) holding **title · channel · duration · url · description · clean transcript**. Then `Read` that file to study/quote/summarize. Capture the path:

```
md=$(scripts/yt-fetch.sh "https://youtu.be/XXXX" /tmp)   # then Read "$md"
```

- **No captions** → the Transcript section says so (nothing to read — pick another source).
- **Unavailable / private / blocked** → exits non-zero with a message.
- Single video only (not playlists). English captions by default.

## Why a wrapper, not a raw command (the traps it handles)

Verified against the yt-dlp docs — the naive one-liner fails in ways the script fixes:
- `--sub-langs "en.*"` is a **regex** that matches *every* English variant (en, en-orig, en-de-DE, en-ja…) → **HTTP 429**. The script uses a bounded exact list `en-orig,en,en-US,en-GB`.
- `--print` **implies `--simulate`** → it silently skips writing files. The script uses `--write-info-json` + `jq`.
- Auto-caption `.vtt` is full of rolling-window duplicate lines; `scripts/vtt2text.py` strips them to clean text (no ffmpeg).

To fetch non-English or more langs, edit `--sub-langs` in `scripts/yt-fetch.sh`. If this stays heavily used, that's the single place to harden it.
