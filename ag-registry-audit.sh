#!/bin/bash
# Audit registry.json against actual project state
# Usage: ag-registry-audit [--fix]
#
# Checks:
#   - All projects in ~/Projects/ are registered
#   - Registered paths exist
#   - Plugin declarations match installed_plugins.json
#   - Skills match actual .claude/skills/ subdirs
#   - Rules match actual .claude/rules/ files
#   - MCPs match actual .mcp.json
#   - Bootstrapped flag matches .memory-bank/ existence

set -e

HUB="$HOME/Projects/agent"
REGISTRY="$HUB/registry.json"
PROJECTS_DIR="$HOME/Projects"
PLUGINS_FILE="$HOME/.claude/plugins/installed_plugins.json"
FIX="${1:---check}"
DRIFT=0

if [ ! -f "$REGISTRY" ]; then
    echo "Error: $REGISTRY not found. Run bootstrap or create manually."
    exit 1
fi

command -v jq &>/dev/null || { echo "Error: jq required"; exit 1; }

red()    { printf "\033[31m%s\033[0m\n" "$1"; }
green()  { printf "\033[32m%s\033[0m\n" "$1"; }
yellow() { printf "\033[33m%s\033[0m\n" "$1"; }

# ============================================
# 1. Check for unregistered projects
# ============================================
echo "=== Checking for unregistered projects ==="
for dir in "$PROJECTS_DIR"/*/; do
    name=$(basename "$dir")
    [ "$name" = "agent" ] && continue
    registered=$(jq -r --arg n "$name" '.projects[$n] // empty' "$REGISTRY")
    if [ -z "$registered" ]; then
        red "  MISSING: $name not in registry"
        DRIFT=$((DRIFT + 1))
    fi
done

# ============================================
# 2. Check registered projects exist
# ============================================
echo "=== Checking registered paths exist ==="
for name in $(jq -r '.projects | keys[]' "$REGISTRY"); do
    path=$(jq -r --arg n "$name" '.projects[$n].path' "$REGISTRY")
    if [ ! -d "$path" ]; then
        red "  STALE: $name -> $path (not found)"
        DRIFT=$((DRIFT + 1))
    fi
done

# ============================================
# 3. Check bootstrapped flag
# ============================================
echo "=== Checking bootstrapped status ==="
for name in $(jq -r '.projects | keys[]' "$REGISTRY"); do
    path=$(jq -r --arg n "$name" '.projects[$n].path' "$REGISTRY")
    registered=$(jq -r --arg n "$name" '.projects[$n].bootstrapped' "$REGISTRY")
    actual=false
    [ -d "$path/.memory-bank" ] && [ -d "$path/.claude" ] && actual=true
    if [ "$registered" != "$actual" ]; then
        yellow "  DRIFT: $name bootstrapped: registry=$registered actual=$actual"
        DRIFT=$((DRIFT + 1))
    fi
done

# ============================================
# 4. Check plugins match installed_plugins.json
# ============================================
echo "=== Checking plugins ==="
if [ -f "$PLUGINS_FILE" ]; then
    for name in $(jq -r '.projects | keys[]' "$REGISTRY"); do
        path=$(jq -r --arg n "$name" '.projects[$n].path' "$REGISTRY")
        registered_plugins=$(jq -r --arg n "$name" '.projects[$n].plugins // [] | sort | join(",")' "$REGISTRY")

        # Find actual plugins installed for this project (project-scoped)
        actual_plugins=$(jq -r --arg p "$path" '
            [.plugins | to_entries[] |
             select(.value | map(select(.scope == "project" and .projectPath == $p)) | length > 0) |
             .key | split("@")[0]] | sort | join(",")
        ' "$PLUGINS_FILE")

        if [ "$registered_plugins" != "$actual_plugins" ]; then
            yellow "  DRIFT: $name plugins: registry=[$registered_plugins] actual=[$actual_plugins]"
            DRIFT=$((DRIFT + 1))
        fi
    done
fi

# ============================================
# 5. Check skills match actual directories
# ============================================
echo "=== Checking skills ==="
for name in $(jq -r '.projects | keys[]' "$REGISTRY"); do
    path=$(jq -r --arg n "$name" '.projects[$n].path' "$REGISTRY")
    registered_skills=$(jq -r --arg n "$name" '.projects[$n].skills // [] | sort | join(",")' "$REGISTRY")

    actual_skills=""
    if [ -d "$path/.claude/skills" ]; then
        actual_skills=$(find "$path/.claude/skills" -mindepth 1 -maxdepth 1 -type d -exec basename {} \; 2>/dev/null | sort | tr '\n' ',' | sed 's/,$//')
    fi

    if [ "$registered_skills" != "$actual_skills" ]; then
        yellow "  DRIFT: $name skills: registry=[$registered_skills] actual=[$actual_skills]"
        DRIFT=$((DRIFT + 1))
    fi
done

# ============================================
# 6. Check rules match actual files
# ============================================
echo "=== Checking rules ==="
for name in $(jq -r '.projects | keys[]' "$REGISTRY"); do
    path=$(jq -r --arg n "$name" '.projects[$n].path' "$REGISTRY")
    registered_rules=$(jq -r --arg n "$name" '.projects[$n].rules // [] | sort | join(",")' "$REGISTRY")

    actual_rules=""
    if [ -d "$path/.claude/rules" ]; then
        actual_rules=$(find "$path/.claude/rules" -maxdepth 1 -name '*.md' -exec basename {} .md \; 2>/dev/null | sort | tr '\n' ',' | sed 's/,$//')
    fi

    if [ "$registered_rules" != "$actual_rules" ]; then
        yellow "  DRIFT: $name rules: registry=[$registered_rules] actual=[$actual_rules]"
        DRIFT=$((DRIFT + 1))
    fi
done

# ============================================
# 7. Check MCPs match actual .mcp.json
# ============================================
echo "=== Checking MCPs ==="
for name in $(jq -r '.projects | keys[]' "$REGISTRY"); do
    path=$(jq -r --arg n "$name" '.projects[$n].path' "$REGISTRY")
    registered_mcps=$(jq -r --arg n "$name" '.projects[$n].mcps // [] | sort | join(",")' "$REGISTRY")

    actual_mcps=""
    if [ -f "$path/.mcp.json" ]; then
        actual_mcps=$(jq -r '.mcpServers // {} | keys | sort | join(",")' "$path/.mcp.json" 2>/dev/null)
    fi

    if [ "$registered_mcps" != "$actual_mcps" ]; then
        yellow "  DRIFT: $name mcps: registry=[$registered_mcps] actual=[$actual_mcps]"
        DRIFT=$((DRIFT + 1))
    fi
done

# ============================================
# Summary
# ============================================
echo ""
if [ "$DRIFT" -eq 0 ]; then
    green "Registry is in sync. No drift detected."
else
    red "Found $DRIFT drift(s)."
    [ "$FIX" != "--fix" ] && echo "Run with --fix to auto-correct registry.json"
fi

exit $DRIFT
