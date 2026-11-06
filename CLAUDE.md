# CLAUDE.md: solar-ablation-de

You (Claude Code) own the implementation and maintenance of this research project end to end.
Fharook is the researcher and decision-maker. You build, run, test, monitor and document. He
decides scientific questions, does the visual audits, and owns the paper.

## Mission

Run a publication-grade ablation study on detecting and segmenting ground-mounted PV farms in
Germany from open satellite imagery (Sentinel-2, Sentinel-1, HLS). The ground truth is the UFZ/MaStR
release V20260203: 10,984 polygons. Every result is reported as a difference from one frozen
reference configuration, broken down by farm-size bin.

- Study design (canonical in-repo copy): `docs/study_design.md`
- Work plan with acceptance criteria: `docs/ROADMAP.md`. Always work from it.
- Decision log (append-only): `docs/decisions.md`
- Every planned experiment: `configs/ablations/registry.yaml`
- Reference configuration: `configs/experiment/reference.yaml`

## Hardware (hard limits, plan around them)

| Resource | Limit | Rules |
| --- | --- | --- |
| GPU | 1 NVIDIA card, 8 GB VRAM | One training job at a time. Always mixed precision (bf16, or fp16 if bf16 is unsupported). Use auto batch size capped at 16 plus gradient accumulation. Turn on gradient checkpointing for ViT backbones. If a model cannot train at batch ≥2, run it frozen-encoder only and record that in decisions.md. |
| RAM | 32 GB | Stream chips from disk; never load the full chip store into memory. `num_workers` ≤ 6. |
| Disk | 500 GB total | Keep a 50 GB safety margin. Run `make disk` before any download or export over 5 GB. Budget in the table below. |

Disk budget (GB, approximate; update after M2 with real numbers):

| Item | GB |
| --- | --- |
| S2 median chips (≈31k chips at 1:3 negatives) | 41 |
| S2 four-season chips (1:1 subset) | 82 |
| S1 chips | 16 |
| HLS chips | 5 |
| Wall-to-wall val+test S2/S1 (for object metrics and T-wall) | 30 |
| Checkpoints (best only per run) | 30 |
| Saved probabilities (reference and best configs only, uint8 COG) | 20 |
| Env, caches, raw downloads (streamed, not kept) | 30 |

Never keep raw scenes. Composite on the server (Google Earth Engine) or stream windows (STAC), then
write the chips.

## Commands

```
make setup      # uv sync; dependencies in pyproject.toml and uv.lock
make labels     # data/raw -> data/interim/labels_v1.gpkg (+ report)
make splits     # 20 km block splits -> data/processed/splits_s1_*
make test       # pytest via uv run
make check      # tests + ruff + disk report before every commit
make disk       # data/runs usage and available disk space
make audit-sample  # M1.3 completeness-audit windows -> runs/audit_m1_3/ (windows.gpkg, audit_form.csv)
make audit-semantics  # M1.5 polygons + review CSV + instructions -> runs/audit_m1_5/ (no .qgs)

Use native Windows PowerShell only. Do not require WSL or Bash. Run Python via uv run.
```
Add new targets to the Makefile as stages are implemented (imagery, chips, train, eval, analysis),
and document them here.

## Scientific invariants (never break these)

1. **The test split is frozen.** `data/processed/splits_s1_*` are not regenerated once the first
   training run has started. Any change needs Fharook's explicit approval and a decisions.md entry.
2. **The test set is evaluated once per configuration**, after selection on validation, via the
   dedicated eval command that logs the event in `runs/test_access.log`. Never pick a checkpoint,
   threshold or hyperparameter on test data.
3. **One factor at a time.** An arm differs from the reference only by its registry overrides.
   Same chip manifest, same step budget, same HPO sweep (`hpo_sweep` in reference.yaml) for every arm.
4. **Normalisation statistics come from training chips only.**
5. **Labels are versioned.** Evaluation always uses label `v1`. Label-ablation arms (F_*) train
   on derived versions only. Never edit `data/raw/`.
6. **Seeds 0, 1, 2 for every arm.** If |Δ vs reference| < 2× the pooled seed SD, add seeds 3 and 4.
7. **Every run is reproducible** from (git hash, resolved config, data-manifest hash, seed).
   Write them to the run folder.
8. **Negative and null results are reported**, never dropped.
9. Ignore index = 255 everywhere (loss and metrics).

## How to work

1. Read `docs/ROADMAP.md`. Take the first unchecked item whose dependencies are met.
2. Plan briefly. If the item needs a human decision or action (see below), ask Fharook and stop.
3. Implement with tests (`tests/`). Keep functions small and typed. Every CLI takes `--config`.
4. Run it. For long jobs (> 10 min) launch in the background (tmux/nohup), write logs to
   `runs/<run_id>/train.log`, make runs resumable from the last checkpoint, and check progress
   instead of blocking.
5. Tick the ROADMAP item, append any decision to `docs/decisions.md`, append results to
   `docs/results_log.md`, and commit (`feat:` / `fix:` / `exp:` / `docs:` prefixes).
6. Before any result goes into a figure or the paper, run the `results-reviewer` subagent. Before
   starting the ablation phase, and after any change to data or splits code, run the
   `leakage-auditor` subagent.

Project skills: `/next-step` (pick and plan the next ROADMAP item), `/run-ablation <arm_id>`
(launch, monitor and register one arm with all seeds), `/status-report` (progress, GPU-hours,
disk, blockers → `docs/status.md`).

## Needs Fharook (ask, don't guess)

- Creating accounts or credentials (Google Earth Engine non-commercial project, Copernicus Data
  Space). Never ask him to paste secrets into chat or into committed files. Use env vars or
  `~/.config`, and keep them gitignored.
- Visual audits: the label completeness audit (M1.3), polygon-semantics check, and the false-positive
  audit (M10). You prepare the sample, the QGIS project and the CSV form. He fills them in.
- Any change to the frozen test split, the reference config after the pilot, or the primary
  metrics.
- Journal choice and paper framing. Not decided yet, so keep everything venue-neutral.

## Conventions

- Python ≥3.11, `src/` layout, package `solarde`. Lint with ruff (line length 120).
- Experiment tracking: MLflow with a local file store at `runs/mlflow`, plus one row per finished
  run in `runs/registry.csv` (arm_id, seed, status, val/test metrics, GPU-hours, git hash).
- CRS: EPSG:3035 for areas, distances and the split grid. Imagery stays in its native UTM grid;
  labels are rasterised into that grid.
- Licence: data under dl-de/by-2-0. Keep attribution to Manske (2026) and BNetzA MaStR in the
  README and in any released derived files.

## Known data facts (measured, do not re-derive unless the data changes)

- 10,984 polygons, 41,823 ha. Label v1: 9,219 positive, 1,765 ignore (area_accuracy_2 661,
  built_after_cutoff 1,257, unlinked 384, commission_date_missing 39, decommissioned 23;
  reasons can overlap).
- 3 polygons lie in Denmark (area_id 10405 Zealand, 10416 Bornholm, 10435 Læsø area). They are
  kept by decision and flagged as `outside_germany_flag`. They need S2 coverage outside the
  German border.
- Median farm 1.66 ha. 38% of farms are under 1 ha but hold 5% of the area. 4.7% are under 20 m
  wide.
- Split s1: 909 blocks with PV. Worst relative balance deviation 1.8%. 132 polygons cross a
  split border and must be masked outside their own block. Region groups: North, West, South, East
  (BKG VG250 Länder, M1.4; the earlier quadrant proxy is archived).
