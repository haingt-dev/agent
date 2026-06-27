#!/usr/bin/env python3
"""Convert a WebVTT subtitle file to clean plain text.

Handles YouTube auto-caption "rolling window" duplication: in auto-subs each cue
carries a settled-prefix line (untagged, repeats prior text) plus a live line with
inline word-timing tags (<00:..:..> / <c>). Keeping only the tagged lines yields the
incremental transcript without the repeats. Manual subs (no tags) fall back to
consecutive-dedup. No ffmpeg needed.

Usage: vtt2text.py <file.vtt>   (prints clean text to stdout)
"""
import re
import sys

raw = open(sys.argv[1], encoding="utf-8", errors="replace").read()
has_tags = bool(re.search(r"<\d\d:\d\d:", raw))
out = []
for ln in raw.splitlines():
    if "-->" in ln or ln.strip() == "WEBVTT" or ln.startswith(("Kind:", "Language:", "NOTE")):
        continue
    tagged = bool(re.search(r"<\d\d:\d\d:|</?c>", ln))
    text = re.sub(r"<[^>]+>", "", ln).strip()
    if not text:
        continue
    # In auto-subs, untagged lines are the repeated settled prefixes — drop them,
    # but keep bracketed sound cues like [Music] / [Applause].
    if has_tags and not tagged and not re.fullmatch(r"\[.*\]", text):
        continue
    if out and text == out[-1]:
        continue
    out.append(text)
print("\n".join(out))
