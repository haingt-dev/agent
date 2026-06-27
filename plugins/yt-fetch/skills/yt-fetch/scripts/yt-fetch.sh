#!/usr/bin/env bash
# yt-fetch — pull a YouTube video's transcript + metadata as readable markdown.
# WebFetch can't read YouTube; this wraps yt-dlp (flags verified against the yt-dlp
# docs) and cleans the auto-caption rolling-window noise into plain text an agent
# can actually read.
#
# Usage: yt-fetch.sh <youtube-url> [output-dir]
#   Writes <output-dir>/<video-id>.md and prints its path to stdout.
#   Exits non-zero if the video can't be fetched; if it has no captions, the
#   Transcript section says so.
set -euo pipefail

URL="${1:?usage: yt-fetch.sh <youtube-url> [output-dir]}"
OUTDIR="${2:-.}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$OUTDIR"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# Bounded exact lang list — NOT a greedy "en.*" regex. Per yt-dlp docs --sub-langs is
# a regex/comma-list; "en.*" matches every English variant (en, en-orig, en-de-DE,
# en-ja, ...) and trips HTTP 429. Prefer the original auto track, then plain en.
# --write-info-json (not --print): --print implies --simulate and would skip writing.
yt-dlp --skip-download \
       --write-auto-subs --write-subs \
       --sub-langs "en-orig,en,en-US,en-GB" \
       --sub-format "vtt" \
       --write-info-json \
       --no-progress --no-warnings \
       -o "$WORK/%(id)s.%(ext)s" \
       "$URL" >&2 || true

INFO="$(find "$WORK" -name '*.info.json' | head -1 || true)"
if [ -z "$INFO" ]; then
  echo "yt-fetch: could not fetch '$URL' (no metadata — video unavailable, private, or blocked)." >&2
  exit 1
fi
ID="$(basename "$INFO" .info.json)"

# Pick the best available English vtt in priority order; fall back to any en*.vtt.
VTT=""
for lang in en-orig en en-US en-GB; do
  if [ -f "$WORK/$ID.$lang.vtt" ]; then VTT="$WORK/$ID.$lang.vtt"; break; fi
done
[ -z "$VTT" ] && VTT="$(find "$WORK" -name "$ID.en*.vtt" | head -1 || true)"

TITLE="$(jq -r '.title // "(unknown title)"' "$INFO")"
UPLOADER="$(jq -r '.uploader // .channel // "(unknown channel)"' "$INFO")"
DUR="$(jq -r '.duration_string // "?"' "$INFO")"
DESC="$(jq -r '.description // ""' "$INFO")"

OUT="$OUTDIR/$ID.md"
{
  echo "# $TITLE"
  echo
  echo "- **Channel:** $UPLOADER"
  echo "- **Duration:** $DUR"
  echo "- **URL:** $URL"
  echo
  echo "## Description"
  echo
  echo "$DESC"
  echo
  echo "## Transcript"
  echo
  if [ -n "$VTT" ] && [ -f "$VTT" ]; then
    python3 "$SCRIPT_DIR/vtt2text.py" "$VTT"
  else
    echo "_(no captions available for this video — nothing to transcribe.)_"
  fi
} > "$OUT"

echo "$OUT"
