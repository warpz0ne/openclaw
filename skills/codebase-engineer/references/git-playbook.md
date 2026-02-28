# Git Playbook

## Quick Routine

1. `git status --short`
2. Inspect changed files/diff
3. Stage only intended files
4. Run checks/tests for touched components
5. Commit with clear intent
6. `git push origin <branch>`

## Staging Discipline

- Prefer explicit paths:
  - `git add path/to/file`
- Avoid broad `git add -A` unless intentional.

## Noisy Files

Keep generated outputs out of commits by default (cache, tmp, local state, large generated JSON) unless required.

## Commit Examples

- `feat: add kriya-availability-only alert behavior`
- `fix: handle skipped monitor runs without notifications`
- `chore: add auto git sync cron task`

## Push Summary Template

- Pushed: `<hash>` to `<branch>`
- Included: `<high-level files/changes>`
- Remaining unstaged/untracked: `<if any>`
