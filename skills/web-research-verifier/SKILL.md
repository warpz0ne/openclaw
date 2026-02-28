---
name: web-research-verifier
description: Perform multi-source web research with source verification and confidence scoring. Use when the user asks for comparisons, market/pricing checks, current events, policy/regulation lookups, vendor evaluation, or any answer that needs fresh external evidence and citations.
---

# Web Research Verifier

Run rigorous, citation-first research quickly.

## Workflow

1. Clarify scope in 1-2 lines (topic, region, time window, output format).
2. Collect sources:
   - Use `web_search` for discovery.
   - Use `web_fetch` for direct extraction.
   - Use `browser` only when pages require JS/login/interaction.
3. Require source diversity:
   - Minimum 3 independent sources for non-trivial claims.
   - Prefer primary sources (official docs, filings, product/pricing pages, regulator sites).
4. Extract structured evidence:
   - claim
   - source URL
   - quote/snippet
   - date observed
5. Resolve conflicts explicitly:
   - If sources disagree, report both and label uncertainty.
6. Output with confidence labels:
   - High: multiple current primary sources agree.
   - Medium: mostly secondary sources or slight conflicts.
   - Low: sparse/dated/conflicting evidence.
7. End with actionable recommendation + what to re-check later.

## Citation Rules

- Attach at least one URL per key claim.
- Mark stale pages when date is old/unclear.
- Do not present unverified claims as facts.
- For pricing: include currency, billing unit, and observed date.

## Fast Heuristics

- Vendor pricing: official pricing page first, docs second, review/blog last.
- Legal/policy: regulator/government/official policy pages first.
- Product capability: official docs + changelog/release notes first.
- Benchmarks: include methodology caveats.

## Output Template

Use this structure unless user requests another format:

1. **Answer in one paragraph**
2. **Key findings** (bullets)
3. **Evidence table**: Claim | Source | Observed date | Confidence
4. **Recommendation**
5. **Known uncertainties / next checks**

For expanded guidance, read `references/checklist.md`.
