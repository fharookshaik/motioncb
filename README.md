# solar-ablation-de

Ablation study: detection and segmentation of ground-mounted PV farms in Germany from open satellite imagery (Sentinel-2, Sentinel-1, HLS). Implementation and maintenance run by Claude Code (see `CLAUDE.md`).

## Quick start (Windows)

1. Put `V20260203.zip` contents under `data/raw/V20260203/gpkg/` and `data/raw/V20260203/csv/`.
2. Install uv and GNU Make, then run `make setup`: installs `uv.lock` dependencies (including CUDA PyTorch) and enables local Git hooks. Do not install PyTorch separately.
3. Check CUDA: `uv run python -c "import torch; print(torch.cuda.is_available())"` must print `True`.
4. On a fresh checkout with raw inputs available, run `make labels`, `make splits`, `make test`. Existing splits are protected: do not regenerate them. Read the retained audit with `make audit-summary`.
5. Start Claude Code in project folder: `claude`. First message: *"Read CLAUDE.md and docs/ROADMAP.md, run /next-step."*

Native Windows PowerShell only. WSL and Bash are not required for project commands. Setup configures `git config --local core.hooksPath .githooks` in each clone; Git for Windows uses its bundled hook launcher.

Project Python entry points use the locked geospatial wheels' bundled projection data, ignoring inherited `PROJ_LIB`, `PROJ_DATA` and `GDAL_DATA` in that process only. PostgreSQL/PostGIS and global environment settings are unchanged.

## Layout

```
CLAUDE.md instructions Claude Code reads session
docs/study_design.md study design (canonical in-repo copy)
docs/ROADMAP.md milestones and acceptance criteria
docs/decisions.md append-only decision log
docs/results_log.md append-only results log
configs/data.yaml label curation settings (label v1)
configs/splits.yaml spatial block split settings (split s1)
configs/experiment/reference.yaml frozen reference configuration
configs/ablations/registry.yaml every planned ablation arm
src/solarde/ package: labels, splits (done); imagery, data, models, train, evaluate, analysis (to build)
.claude/skills/ /next-step, /run-ablation, /status-report
.claude/agents/ leakage-auditor, results-reviewer (independent reviewers)
```

## Data licence and attribution

Ground truth: Manske, D. (2026). *Geo-locations and System Data of Renewable Energy Installations in Germany* (V20260203). Zenodo. https://doi.org/10.5281/zenodo.20716459. Source: BNetzA Marktstammdatenregister. Licence: dl-de/by-2-0. Derived label files keep attribution.

Independent test labels: Krikau & Keller (FIZ Karlsruhe), KIT RADAR PV reference labels, Hesse/NRW. Source: https://b2find.eudat.eu/dataset/a788c3e6-6a4a-529e-97cc-92829fac155d. Licence: **CC BY-SA 4.0**, distinct from UFZ/MaStR; attribution and ShareAlike apply to adapted KIT labels. BKG VG250 boundaries retain their source attribution.
