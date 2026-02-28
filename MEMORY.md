# MEMORY.md

## User Profile
- Name/preferred address: **guru**
- Preferred assistant vibe: **calm**
- Timezone: **ET**
- Timestamp preference: use **Eastern Time** by default in alerts/messages unless explicitly requested otherwise.

## Working Style Preferences
- Wants iterative product work with quick turnaround and direct edits.
- Prefers committing locally continuously and pushing to GitHub only after explicit approval.
- Current repo workflow approved on `main` branch.

## Active Project: Slice Dashboard
- Building and refining a personal dashboard called **Slice**.
- Recent requested features include:
  - Source-specific news cards
  - Sticky tab persistence across refresh
  - Drag-and-drop reorder for news cards (by header)
  - Finance tab UI refinements (e.g., top table label)

## Git / Infrastructure
- GitHub repo: `warpz0ne/openclaw`
- SSH key auth configured for pushing from VPS.
- VPS capacity check done: sufficient CPU/RAM/disk for app + local DB; swap suggested.

## Personal Finance App Direction
- User wants a finance/investment cockpit with:
  - Net worth, growth rates, investment performance over time
  - IRR/TWR and benchmark comparisons
  - Monthly categorized expense snapshots with drill-down by transaction
- Data aggregation choice: **Plaid**
- Sync preference: **daily**
- Data masking preference: mask account numbers, keep merchant names visible
- MVP institution scope: **Schwab, Fidelity, M1**
- Backup direction under consideration: prefers secure cloud backup path (asked about AWS S3)

## Privacy / Trust Preferences
- Explicitly asked what model/session knows and persists; values transparency and data handling clarity.
- Wants memory maintained periodically for better assistant continuity.
- Strong preference for data minimization: avoid storing personal data unless absolutely necessary for communication/workflow.

## New Project Candidate (2026-02-27)
- User wants to build an enduring, agentic product that solves everyday problems for common people, with sub-agent orchestration.
- Top shortlisted ideas: **Medical Bill Defense Copilot** and **Benefits & Aid Navigator**.
- Current focus selected for deeper exploration: **Medical Bill Defense Copilot**.
- Budget signal: willing to invest up to **$500** initially for cloud/agent expansion (Hostinger vs GCP based on economics).
- User asked to save this project context and return later to begin implementation.

## Continuity Protocol (2026-02-28)
- User explicitly asked to stop losing overnight context and maintain stronger continuity between sessions.
- Continuity system established:
  - `NOW.md` tracks active objective, immediate next actions, and session handoff.
  - `memory/YYYY-MM-DD.md` captures same-day checkpoints.
  - `MEMORY.md` keeps only durable preferences/decisions.
- Expectation: maintain this flow proactively so returning context is immediately available.

## Slice Auth UX Direction (2026-02-28)
- Domain confirmed: `dudda.cloud`.
- User wants professional login UX with branding consistency and no clunky Google iframe/chip appearance after logout.
- Decision: move to custom OAuth button + server-side Google auth callback flow for tighter UX control.
- Added reusable ops helper in repo: `tools/ops/slicectl.sh` (status/restart/log/test/env). 
