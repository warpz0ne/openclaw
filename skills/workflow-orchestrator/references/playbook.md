# Orchestration Playbook

## Task Graph Pattern

1. Intake and scope lock
2. Discovery and evidence collection
3. Build/execute subtasks (parallel where safe)
4. Validation checkpoint
5. Synthesis and delivery
6. Follow-up scheduling (optional)

## Parallelization Checklist

Parallelize only if all are true:
- No shared mutable files/resources
- No ordering dependency
- No shared rate limit likely to throttle all workers
- Merge format is predefined

## Retry Matrix

- Network timeout / 429 / 5xx: retry (max 2-3)
- Auth error / permission denied: fail fast, request action
- Validation mismatch: fail and revise task contract
- Tool unavailable: switch fallback tool or isolate and continue

## Sub-Agent Task Contract Template

- **Task:**
- **Inputs provided:**
- **Constraints:**
- **Output format:**
- **Timeout:**
- **Definition of done:**

## Merge Rules

- Normalize outputs to one schema before synthesis.
- Deduplicate overlapping findings.
- Preserve source attribution where relevant.
- Highlight unresolved conflicts explicitly.

## Final Delivery Checklist

- Clear answer first
- Evidence/artifacts linked
- Risks and assumptions explicit
- Next best action suggested
