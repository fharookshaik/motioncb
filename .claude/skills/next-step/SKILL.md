---
name: next-step
description: Pick the next unchecked item from docs/ROADMAP.md, check its dependencies and plan it. Use at the start of a work session or when asked "what's next".
---

# Next step

1. Read `docs/ROADMAP.md`, the last 20 lines of `docs/decisions.md` and `docs/status.md` if it exists.
2. Find the first unchecked item whose earlier items are done. If it is marked `[H]`, prepare
   everything that does not need Fharook. Then tell him exactly what he must do, and stop.
3. Check resources first: `nvidia-smi` (is a job already running?) and `make disk`. If a training
   job is running, pick a CPU-only item instead (code, tests, analysis), or report progress.
4. Write a short plan: files to create or change, tests to add, the commands that prove the
   acceptance criterion, and the expected disk and GPU cost.
5. Carry it out, run the acceptance check, tick the box, log any decisions, commit.
