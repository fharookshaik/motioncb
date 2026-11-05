---
name: run-ablation
description: Launch, monitor and register one ablation arm from configs/ablations/registry.yaml (all seeds, equal-budget HPO, val selection, single logged test evaluation). Use when asked to run an arm or continue the ablation queue.
---

# Run one ablation arm

Argument: an arm id such as `B_drop_swir`. If none is given, take the next arm in the ROADMAP M7 order
that is not yet `done` in `runs/registry.csv`.

## Pre-flight (abort with a clear message if any check fails)
- The arm exists in `configs/ablations/registry.yaml`, and its `depends_on` arms are done.
- The reference r1 is frozen (ROADMAP M6 ticked).
- The arm's imagery or label version exists in `data/processed/manifest_*.json`. If not, build it
  first and check the disk budget.
- No other GPU job is running (`nvidia-smi`). There is ≥ 50 GB free disk.
- The resolved config differs from the reference ONLY in the registry overrides. Print the diff
  and include it in the run folder.

## Run
1. HPO sweep (`hpo_sweep` in reference.yaml) on seed 0, with selection on `val/object_f1_large`.
   Use exactly the same sweep size as every other arm.
2. Train seeds 0, 1, 2 with the selected hyperparameters, in the background and resumable. Logs go
   to `runs/<arm>/<seed>/train.log`. Poll every ~10 minutes, report progress, and never block for hours.
3. Validation evaluation with all metrics.
4. Test evaluation, once, through `make eval-test RUN=<arm>/<seed>` (logs to `runs/test_access.log`).
5. Append to `runs/registry.csv`: arm, seed, status, key val/test metrics, GPU-hours, git hash,
   manifest hash.
6. Compute the paired block-bootstrap Δ vs the reference. If |Δ| < 2× the pooled seed SD, queue
   seeds 3 and 4.
7. Append a short entry to `docs/results_log.md`: arm, Δ primary metrics with CI, one-line reading.
   Do not interpret beyond the numbers.

## On failure
CUDA OOM: halve the micro-batch and double accumulation (effective batch unchanged), then retry
once. If it still fails, mark the arm `blocked` in the registry with the reason, log it in
decisions.md and move on.
