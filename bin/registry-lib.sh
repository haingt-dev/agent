#!/bin/bash
# Shared registry helpers — sourced by BOTH bin/ag-registry-audit.sh and
# .claude/scripts/registry-check.sh so the narrative-sync check lives in ONE place
# (the guard itself must not drift between the two consumers).

# check_narrative_sync <registry_path>
# Guarantees the project the registry marks `status:primary` is the SAME one the
# always-loaded narrative surfaces crown — the recurring "pivoted registry, forgot
# the narrative" drift. Convention (keep these markers + the project name on one line):
#   - indie-ecosystem.md : the primary's row is tagged "center of gravity"
#   - core-memory.md     : a line states "PRIMARY BUILD = <project>"
# Prints "  DRIFT: ..." lines for any mismatch; returns the number of issues (0 = clean).
check_narrative_sync() {
    local reg="$1" issues=0 primary n
    local eco="$HOME/.claude/brains/indie-ecosystem.md"
    local core="$HOME/.claude/core-memory.md"

    primary=$(jq -r '.projects | to_entries[] | select(.value.status=="primary") | .key' "$reg" 2>/dev/null)
    n=$(printf '%s\n' "$primary" | grep -c .)
    if [ "$n" -ne 1 ]; then
        echo "  DRIFT: registry has $n projects with status:primary (expect exactly 1)"
        return 1
    fi

    if [ -f "$eco" ] && ! grep -i 'center of gravity' "$eco" | grep -q "$primary"; then
        echo "  DRIFT: indie-ecosystem.md 'center of gravity' line does not name registry primary '$primary'"
        issues=$((issues + 1))
    fi
    if [ -f "$core" ] && ! grep -i 'primary build' "$core" | grep -qi "$primary"; then
        echo "  DRIFT: core-memory.md 'PRIMARY BUILD' line does not name registry primary '$primary'"
        issues=$((issues + 1))
    fi
    return $issues
}
