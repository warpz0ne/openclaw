---
name: workflow-orchestrator
description: Orchestrate multi-step and multi-agent work reliably. Use when tasks should be decomposed into parallelizable units, delegated to sub-agents, retried on failure, and merged into one coherent output with status tracking and risk controls.
---

# Workflow Orchestrator

Coordinate complex work with predictable execution.

## Core Loop

1. Define objective, constraints, and done criteria.
2. Decompose into task graph:
   - serial dependencies
   - parallel-safe tasks
   - validation checkpoints
3. Assign execution mode per task:
   - direct tool call
   - sub-agent session
   - deferred cron job
4. Execute with controls:
   - timeout per task
   - retry budget
   - fallback path
5. Merge outputs and run quality checks.
6. Return concise summary + artifacts + open risks.

## Decomposition Rules

- Split by independent deliverables, not arbitrary size.
- Keep each task single-purpose and testable.
- Isolate risky actions (external writes, deletes, payments) into explicit approval gates.
- Prefer parallel execution only when inputs do not overlap.

## Delegation Guidance

- Use sub-agents for long/complex jobs.
- Pass clear task contracts:
  - input assumptions
  - exact output format
  - stop conditions
- Keep final synthesis in the primary session.

## Reliability Controls

- Timeout every delegated task.
- Retry transient failures (network/rate-limit) with bounded attempts.
- Do not retry deterministic failures without changing approach.
- Preserve partial progress; avoid restarting whole workflow unless required.

## Output Contract

Always provide:
- Objective completed/not completed
- Completed steps
- Pending/blocked steps
- Risks and confidence
- Next action options

## Lightweight Status Template

- **Goal:** ...
- **State:** running | blocked | complete
- **Completed:** ...
- **Blocked by:** ...
- **Next step:** ...

For patterns and checklists, read `references/playbook.md`.
