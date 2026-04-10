"""brain_radar: Project awareness — scan projects, hot files, brain topics, file reference graph."""

import re
import sqlite3
import subprocess
import time
from pathlib import Path


PROJECTS_DIR = Path.home() / "Projects"
ECOSYSTEM_PROJECTS = {"digital-identity", "Wildtide", "Bookie", "portfolio"}


def brain_radar(
    conn: sqlite3.Connection,
    project: str | None = None,
    scope: str | None = None,
) -> dict:
    """
    Main entry point for brain_radar.

    Args:
        project: Focus on a single project (e.g., "Wildtide"). Scans only that directory.
        scope: Override — "all" (every project) or "ecosystem" (4 core projects).
               If neither project nor scope given, scans all projects.

    Returns a dict with keys:
      - projects: list of git project status dicts
      - hot_files: list of recently modified file paths
      - brain_topics: list of active brain tags with counts
      - recent_tags: list of tag names only (convenience subset)
      - file_graph: adjacency dict of markdown file references
      - processes: list of active relevant processes (if any found)
    """
    scan_dirs = _resolve_scan_dirs(project, scope)
    result: dict = {}

    try:
        result["projects"] = _scan_projects(scan_dirs)
    except Exception:
        result["projects"] = []

    try:
        result["hot_files"] = _scan_hot_files(scan_dirs)
    except Exception:
        result["hot_files"] = []

    try:
        result["brain_topics"] = _brain_topics(conn, project=project)
    except Exception:
        result["brain_topics"] = []

    try:
        result["recent_tags"] = _brain_topics(conn, names_only=True, project=project)
    except Exception:
        result["recent_tags"] = []

    try:
        result["file_graph"] = _scan_file_references(scan_dirs)
    except Exception:
        result["file_graph"] = {}

    try:
        procs = _active_processes()
        if procs:
            result["processes"] = procs
    except Exception:
        pass

    return result


def _resolve_scan_dirs(project: str | None, scope: str | None) -> list[Path]:
    """Resolve which directories to scan based on project/scope."""
    if scope == "all" or (project is None and scope is None):
        return sorted(
            d for d in PROJECTS_DIR.iterdir() if d.is_dir() and (d / ".git").exists()
        )
    elif scope == "ecosystem":
        return sorted(
            PROJECTS_DIR / name
            for name in ECOSYSTEM_PROJECTS
            if (PROJECTS_DIR / name).is_dir()
        )
    else:
        project_path = PROJECTS_DIR / project
        if project_path.is_dir():
            return [project_path]
        return []


def _scan_projects(scan_dirs: list[Path]) -> list[dict]:
    """
    Scan given directories for git repos and return status for each.

    Returns list of dicts: {name, branch, modified, last_commit, age}
    or {name, error} on failure.
    """
    results = []

    for entry in scan_dirs:
        if not entry.is_dir():
            continue
        if not (entry / ".git").exists():
            continue

        name = entry.name
        info: dict = {"name": name}

        try:
            # Current branch
            branch_result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                cwd=entry,
                timeout=5,
            )
            info["branch"] = branch_result.stdout.strip() or "detached"

            # Modified file count
            status_result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                cwd=entry,
                timeout=5,
            )
            modified_lines = [
                l for l in status_result.stdout.splitlines() if l.strip()
            ]
            info["modified"] = len(modified_lines)

            # Last commit message + relative age
            log_result = subprocess.run(
                ["git", "log", "-1", "--format=%s|%cr"],
                capture_output=True,
                text=True,
                cwd=entry,
                timeout=5,
            )
            log_output = log_result.stdout.strip()
            if log_output:
                # Split on last | to separate message from age
                last_pipe = log_output.rfind("|")
                if last_pipe != -1:
                    msg = log_output[:last_pipe]
                    age = log_output[last_pipe + 1:]
                else:
                    msg = log_output
                    age = ""
                info["last_commit"] = msg[:50]
                info["age"] = age
            else:
                info["last_commit"] = ""
                info["age"] = ""

        except Exception:
            info = {"name": name, "error": "git failed"}

        results.append(info)

    return results


def _scan_hot_files(scan_dirs: list[Path], hours: int = 24, limit: int = 8) -> list[str]:
    """
    Find files modified in the last N hours across given directories.

    Returns paths relative to ~/Projects/, sorted by mtime descending.
    """
    extensions = {".md", ".py", ".gd", ".ts", ".sh"}
    skip_parts = {".claude", "worktrees", ".git", "node_modules"}

    cutoff = time.time() - (hours * 3600)
    candidates: list[tuple[float, Path]] = []

    try:
        for scan_dir in scan_dirs:
            if not scan_dir.exists():
                continue
            for ext in extensions:
                for filepath in scan_dir.rglob(f"*{ext}"):
                    # Skip paths containing any skip directory component
                    parts = set(filepath.parts)
                    if parts & skip_parts:
                        continue
                    # Also check string-based worktrees path segment
                    if "worktrees" in str(filepath):
                        continue

                    try:
                        mtime = filepath.stat().st_mtime
                        if mtime >= cutoff:
                            candidates.append((mtime, filepath))
                    except OSError:
                        continue
    except Exception:
        pass

    candidates.sort(key=lambda x: x[0], reverse=True)
    relative_paths = []
    for _, fp in candidates[:limit]:
        try:
            relative_paths.append(str(fp.relative_to(PROJECTS_DIR)))
        except ValueError:
            relative_paths.append(str(fp))

    return relative_paths


def _brain_topics(
    conn: sqlite3.Connection,
    days: int = 60,
    limit: int = 12,
    names_only: bool = False,
    project: str | None = None,
) -> list:
    """
    Query the brain DB for the most active tags in the last N days.

    Excludes noise tags (auto-captured, web-search, etc.).
    Returns list of {"tag": ..., "count": ...} dicts, or tag names if names_only=True.
    """
    noise_tags = [
        "auto-captured",
        "web-search",
        "web-fetch",
        "pre-compact",
        "auto-snapshot",
        "structured",
        "auto-extracted",
        "synthesized",
        "entity",
        "skill",
    ]
    placeholders = ",".join("?" * len(noise_tags))

    project_filter = ""
    params = list(noise_tags)
    if project:
        project_filter = " AND memories.project = ?"
        params.append(project)

    sql = f"""
        SELECT value as tag, COUNT(*) as n
        FROM memories, json_each(memories.tags)
        WHERE created_at > datetime('now', '-{days} days')
        AND value NOT IN ({placeholders})
        {project_filter}
        GROUP BY value
        ORDER BY n DESC
        LIMIT {limit}
    """

    try:
        rows = conn.execute(sql, params).fetchall()
    except Exception:
        return []

    if names_only:
        return [row["tag"] for row in rows]
    return [{"tag": row["tag"], "count": row["n"]} for row in rows]


def _scan_file_references(scan_dirs: list[Path]) -> dict:
    """
    Phase 2 — file reference graph.

    Scan .md files across given directories for links to other files.
    Returns adjacency dict: {relative_filepath: [list_of_refs], ...}
    Only includes entries with at least 1 reference.
    """
    skip_segments = {"node_modules", ".git", "reference", "derived", "worktrees"}

    graph: dict[str, list[str]] = {}

    try:
        for scan_dir in scan_dirs:
            if not scan_dir.exists():
                continue
            for md_file in scan_dir.rglob("*.md"):
                # Skip paths containing any skip segment
                path_parts = set(md_file.parts)
                if path_parts & skip_segments:
                    continue

                try:
                    content = md_file.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue

                refs: list[str] = []

                # 1. Markdown links: [text](path.md)
                md_links = re.findall(r'\[.*?\]\(([^)]+\.md)\)', content)
                refs.extend(md_links)

                # 2. @-references: @~/path or @/path
                at_refs = re.findall(r'@(~?/[^\s\)]+)', content)
                refs.extend(at_refs)

                # 3. "ref/see" patterns: ref `path.md` or see path.md
                ref_see = re.findall(
                    r'(?:ref|see)\s+[`"]?([^\s`"]+\.md)', content, re.IGNORECASE
                )
                refs.extend(ref_see)

                if refs:
                    try:
                        rel_path = str(md_file.relative_to(PROJECTS_DIR))
                    except ValueError:
                        rel_path = str(md_file)
                    graph[rel_path] = refs

    except Exception:
        pass

    return graph


def _active_processes() -> list[str]:
    """
    Check for relevant active processes (godot, uvicorn, node server).

    Returns up to 4 lines of process info, or empty list on failure.
    """
    try:
        result = subprocess.run(
            ["pgrep", "-la", "godot|uvicorn|node.*server"],
            capture_output=True,
            text=True,
            timeout=3,
        )
        lines = [l for l in result.stdout.splitlines() if l.strip()]
        return lines[:4]
    except Exception:
        return []
