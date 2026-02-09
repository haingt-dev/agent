# Kilo Code & Antigravity Unified Global Rules

## 1. Core Directives
**CRITICAL**: Maintain a stable and clean state. Do not leave the user's environment in a broken or "dirty" state without explicit permission or during an active debugging session.

## 2. Memory Bank Protocol (Shared Context)
**Location**: `.agent/rules/memory-bank`
*This directory is the shared source of truth for both Kilo Code and Antigravity agents.*

1.  **Read on Start**: At the start of **EVERY** task, you **MUST** read the following files to ground yourself in the project context:
    *   `brief.md`
    *   `product.md`
    *   `context.md`
    *   `architecture.md`
    *   `tech.md`
2.  **Maintain**: Update these files (especially `context.md`) immediately if you make significant architectural changes or complete major tasks.
3.  **Initialization**: If the Memory Bank is missing, you must proactively offer to initialize it for the user.
4.  **Source of Truth**: When in doubt about scope or style, refer to these files.

## 3. Documentation Proactiveness
**CRITICAL**: Knowledge rot is the enemy. Keep documentation synchronized with code changes.

1.  **Immediate Updates**: Update documentation (README, internal docs, etc.) in the **same commit** as the code change.
2.  **Self-Correction**: If you encounter a discrepancy between documentation and reality, you **MUST** fix it.

## 4. Execution & Commit Protocol
**Restriction**: A task is **NOT** "done" until the code is safely committed.

**Workflow**:
1.  **Verify**: Ensure changes are correct and tests pass.
2.  **Stage**: `git add .`
3.  **Commit**: `git commit -m "<type>(<scope>): <description>"`
4.  **Retry**: If commit fails, FIX and RETRY immediately.

**Commit Types**:
*   `feat`: New feature
*   `fix`: Bug fix
*   `docs`: Documentation only
*   `style`: Formatting, white-space
*   `refactor`: Code change (no fix/feat)
*   `perf`: Performance improvement
*   `test`: Adding/fixing tests
*   `chore`: Build/tools maintenance
