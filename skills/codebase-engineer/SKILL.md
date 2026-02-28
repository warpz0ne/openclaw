---
name: codebase-engineer
description: Execute software changes with a disciplined workflow: clarify scope, plan, edit minimally, run tests/lint, verify diffs, commit with clear messages, and push safely. Use for feature work, bug fixes, refactors, and release-ready code updates.
---

# Codebase Engineer

Use this workflow for reliable, low-drama shipping.

## Default Flow

1. Clarify objective + constraints (scope, files, risk).
2. Inspect current code paths before editing.
3. Make minimal, focused edits.
4. Run relevant checks:
   - unit/integration tests for changed areas
   - lint/format where applicable
5. Review diff for unintended changes.
6. Commit with clear message (type + intent + scope).
7. Push only when requested or policy allows.

## Commit Policy

- Prefer small commits with single purpose.
- Message format:
  - `feat: ...`
  - `fix: ...`
  - `chore: ...`
  - `refactor: ...`
  - `docs: ...`
- Include context in body when behavior changes.

## Git Safety Rules

- Never use destructive history edits unless explicitly asked.
- Avoid committing generated/noisy artifacts unless required.
- Confirm branch before push.
- Show concise summary after push (branch + commit hash).

## Review Checklist (before commit)

- Does code solve the stated task only?
- Any accidental file changes?
- Any secrets/tokens in diff?
- Tests/checks passed for touched behavior?
- Backward compatibility concerns noted?

For details, read `references/git-playbook.md`.
