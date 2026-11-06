# ROADMAP

Claude Code works top to bottom. An item is done only when its **acceptance** criterion is met and
checked. `[H]` marks a task that needs Fharook. Prepare everything around it, then ask him.

## M0: Environment
- [x] M0.1 Create the Python 3.11 uv environment from `pyproject.toml` and `uv.lock`. Install torch with the CUDA build matching
  the driver (`nvidia-smi`). Use Windows PowerShell for all project commands; do not require WSL or Bash.
  *Acceptance:* `uv run python -c "import torch; print(torch.cuda.is_available())"` prints True. `make test` passes.
- [x] M0.2 GPU probe script `scripts/gpu_probe.py`: VRAM, bf16 support, max batch for U-Net-R50 at
  256 px with 10 bands. *Acceptance:* results appended to docs/decisions.md.
- [x] M0.3 `git init`, first commit, pre-commit hook running `make check`.

## M1: Labels and splits
- [x] M1.1 Label curation (`make labels`) → label v1. Done 2026-11-03: 9,219 positive / 1,765 ignore.
- [x] M1.2 Block splits (`make splits`) → split s1. Done 2026-11-03: worst deviation 2.2%.
- [x] M1.3 [H] Completeness audit. Script `scripts/make_audit_sample.py`: draw 60 random 5×5 km
  windows inside test+val blocks, stratified by region. Export a QGIS project (labels v1 + S2
  composite + a freely viewable high-res basemap, used for inspection only) and a CSV form
  (window_id, missing_pv_count, notes). Fharook fills it in.
  *Acceptance:* omission rate with a 95% CI written to docs/results_log.md.
- [x] M1.4 Replace the region proxy (lon 10.5 / lat 51.0) with BKG VG250 Länder groups if it
  changes assignments materially. Otherwise keep it and document why. Must be done **before
  M6**, because the split freezes then.
  Done 2026-11-06: 4 Land groups (North, West, South, East), split s1 regenerated; see decisions.md.
- [x] M1.5 Polygon semantics documented from author methodology instead of a 100-polygon visual review.
  *Revised acceptance:* source-backed paragraph in decisions.md, explicitly distinguishing intended
  mapping convention from independently verified release-wide adherence.
  Done 2026-11-06: Manske et al. (2022), §3.2 defines outer edges of coherent PV modules,
  not fences; V20260203 cites this methodology. Manual review waived at Fharook's request.
  Obsolete sampler, tests, guide and generated files removed after closure; three partial CSV
  entries preserved in decisions.md. No release-wide independent validation claimed.
- [x] M1.6 Download V20250101 (Zenodo 16942382) and build test set T-new (new polygons inside
  test blocks). Download the KIT RADAR manual labels for T-indep.
  Done 2026-11-06 with substitute V20240104 (Zenodo 14627853, open) because V20250101 is restricted:
  504 of 2,230 test polygons. KIT labels downloaded and md5-verified (84 tiles). T-indep scope needs
  Fharook; see decisions.md.

## M2: Imagery pipeline
- [ ] M2.1 Backend benchmark: (a) Google Earth Engine `computePixels` with server-side
  compositing (needs [H] a non-commercial GEE project), (b) STAC (Planetary Computer / Earth
  Search) + odc-stac windowed reads. Time 50 chips each.
  *Acceptance:* backend choice plus throughput in decisions.md.
- [ ] M2.2 S2 reference composite for all chips (median, Apr–Sep 2025, Cloud Score+ or
  SCL+s2cloudless, BOA offset handled). Resumable and idempotent: skip chips that already
  exist and are valid.
- [ ] M2.3 Wall-to-wall S2 composite for all val+test blocks (land only, Germany plus the Danish
  sites).
- [ ] M2.4 S1 (VV, VH median and SD, dB), HLS 30 m, and S2 single-scene and four-season
  composites for the arms that need them.
- [ ] M2.5 Data manifest `data/processed/manifest_<name>.json` (chip list, hashes, band order,
  nodata stats). *Acceptance:* `make disk` within budget; random chip QA PNGs in
  `runs/qa/` look right.

## M3: Chip dataset
- [ ] M3.1 Chip sampler: positives (any positive pixel), negatives stratified by
  WorldCover/CORINE at 1:3 (the 1:1 subset is nested), border-buffer filter, cross-split polygons
  masked to 255. Fixed, hashed chip list per split.
- [ ] M3.2 Rasterise labels into each chip's native grid, both hard and fractional (1 m → 10 m).
- [ ] M3.3 PyTorch Dataset/DataModule (GeoTIFF or Zarr), train-only normalisation stats, augmentations.
  *Acceptance:* unit tests for mask alignment (overlay QA images) and normalisation leakage.

## M4: Training framework
- [ ] M4.1 Lightning module + Hydra configs that compose `reference.yaml` + one registry arm.
  Backbones from segmentation-models-pytorch, TorchGeo (SSL4EO weights) and TerraTorch (GFMs).
- [ ] M4.2 Resumable training, MLflow logging, `runs/<arm>/<seed>/` folder with resolved
  config, git hash and manifest hash.
- [ ] M4.3 Equal-budget HPO sweep runner (`hpo_sweep`), with selection on val only.

## M5: Evaluation
- [ ] M5.1 Sliding-window inference over whole blocks (overlap 25%, cosine blending).
- [ ] M5.2 Metrics: accumulated PV IoU, pixel P/R/F1, object detection (≥10% cover) and
  delineation (IoU ≥0.5), recall per size bin and per mounting type, boundary F1 (1 px), area
  error, false positives per 1,000 km², cost metrics.
- [ ] M5.3 Block-bootstrap CIs, paired Δ vs reference, Holm correction.
  *Acceptance:* tests against hand-computed toy examples.
- [ ] M5.4 Test-access guard: test eval only through `make eval-test RUN=…`, logged to
  `runs/test_access.log`, refused twice for the same run.

## M6: Pilot (freezes the reference)
- [ ] M6.1 Reference r1 with 3 seeds. Measure GPU-hours, seed SD and VRAM fit of every GFM backbone.
- [ ] M6.2 Set `max_steps` and the minimum effect sizes from the pilot. [H] Fharook confirms.
  Pre-register hypotheses (export docs/study_design.md to OSF or similar).
- [ ] M6.3 Run the `leakage-auditor` subagent. *Acceptance:* no findings left open.

## M7: Tier 1 ablations (A, B, C_single/seasonal4, E, F, G, J)
- [ ] M7.1 Queue via `/run-ablation`, one arm at a time. Order: J (free) → B → A → C → F → E → G.
- [ ] M7.2 Run `/status-report` after every 5 arms.

## M8: Tier 2 ablations (C_monthly6, D, H, I), only if the budget remains

## M9: Generalisation and robustness
- [ ] T-region (leave-one-region-out), T-new, T-indep, T-wall, and 5-fold CV for the reference and
  the best configuration.

## M10: Analysis and paper assets
- [ ] [H] False-positive audit (top 200 by confidence) → error taxonomy.
- [ ] Figures 1–7 and Tables 1–3 (see study design), generated by scripts in `src/solarde/analysis/`.
- [ ] Run the `results-reviewer` subagent on every number in the paper tables.
- [ ] Release package: configs, split files, derived masks (with dl-de/by-2-0 attribution), code tag.

## Maintenance (ongoing)
- Weekly: `make check`, `/status-report`, prune checkpoints that are not best-of-run.
- Pin dependency upgrades. Never upgrade torch/terratorch in the middle of an axis.
- Any bug fix that affects completed runs: decide in decisions.md whether to re-run, and list
  which arms.
