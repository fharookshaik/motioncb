---
name: status-report
description: Summarise project progress (ROADMAP items, ablation arms done/pending/blocked, GPU-hours used vs budget, disk usage, open questions for Fharook) into docs/status.md. Use weekly, after every 5 arms, or when asked for status.
---

# Status report

Write `docs/status.md`, replacing the previous one; git keeps the history. Sections:

1. **Headline**: one sentence on where the project stands and what runs next.
2. **ROADMAP**: milestones done / in progress / blocked.
3. **Ablations**: one table per tier with arm, status, seeds done, Δ primary metrics vs reference
   (with CI if available), from `runs/registry.csv`.
4. **Budget**: GPU-hours used vs `budget_estimate_gpu_hours`, a projected finish date for Tier 1
   at the current rate, and disk use vs budget (`make disk`).
5. **Needs Fharook**: every open `[H]` item and every question waiting for a decision, each one
   line, specific.
6. **Risks**: anything trending badly (OOMs, seed variance larger than effects, disk headroom
   below 50 GB).

Keep it under one page. Show numbers, not adjectives.
