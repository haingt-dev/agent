# Auto-Commit Rule

**CRITICAL INSTRUCTION:** You are STRICTLY FORBIDDEN from using the `attempt_completion` tool until you have successfully committed your changes to git.

Before you can finish any task, you MUST execute the following sequence:

1.  **Verify**: Ensure all tests pass and the code is stable.
2.  **Stage**: Run `git add .` to stage all changes.
3.  **Commit**: Run `git commit -m "type(scope): description"`
    *   **Format**: `<type>(<scope>): <description>`
    *   **Types**: `feat`, `fix`, `docs`, `style`, `refactor`, `perf`, `test`, `chore`
    *   **Example**: `feat(auth): add login validation`
4.  **Retry**: If the commit fails (e.g., due to hooks), you MUST fix the issue and try to commit again.

**ONLY** after the `git commit` command returns successfully are you allowed to use `attempt_completion`.
