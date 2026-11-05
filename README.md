# solar-ablation-de

Ablation study: detection and segmentation of ground-mounted PV farms in Germany from open satellite imagery (Sentinel-2, Sentinel-1, HLS). Implementation and maintenance run by Claude Code (see `CLAUDE.md`).

## Quick start (Windows)

1. Put `V20260203.zip` contents under `data/raw/V20260203/gpkg/` and `data/raw/V20260203/csv/`.
2. Install uv, then create environment: `make setup`. Run project commands through `uv run`.
3. Install PyTorch CUDA matching driver shown by `nvidia-smi`; use install command from https://pytorch.org/get-started/locally/.
4. Check: `make labels`, `make splits`, `make test`.
5. Start Claude Code in project folder: `claude`. First message: *"Read CLAUDE.md and docs/ROADMAP.md, run /next-step."*

Native Windows PowerShell only. WSL and Bash are not required.

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
