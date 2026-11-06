# MotionCB — Solar PV detection research core

A research platform for ground-mounted PV farm detection and segmentation in Germany from open satellite imagery (Sentinel-2 reference, Sentinel-1 and HLS experiments). The checkout contains validated label curation, spatial split verification, bounded pilot mask preparation, single-scene Sentinel-2 alignment QA, ignore-aware pixel metrics, and probability-raster polygon export. Reference compositing, model training, inference, API, and map UI remain in progress. Raw data and checkpoints are not bundled in Git.

## Quick start

1. Install Python 3.11 and `uv`.
2. Install core/dev/GIS dependencies: `uv sync --extra dev --extra geo`.
3. Run checks: `uv run pytest -q` and `uv run ruff check src tests`.
4. Import the original local ZIP with `uv run python -m solarde.data.raw --config configs/data.yaml --archive /path/to/V20260203.zip`, then curate with `uv run python -m solarde.labels.curate --config configs/data.yaml`.
5. Review `docs/decisions.md` before initial split creation. Verify existing outputs with `uv run python -m solarde.splits.verify --config configs/splits.yaml --rebuild-check`.
6. Prepare pilot masks with `uv run python -m solarde.data.chips --config configs/preparation.yaml`; acquire exploratory QA with `uv run python -m solarde.imagery.preview --config configs/preparation.yaml`.

Use direct `uv run` commands from PowerShell, macOS, or Linux shells. The current Makefile uses PowerShell syntax.

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
docs/IMPLEMENTATION_AUDIT.md implementation audit
docs/ARCHITECTURE.md current and target architecture
docs/SETUP.md environment and local commands
docs/API.md API status and planned contract
docs/VALIDATION_REPORT.md current checks and acceptance status
```

Prediction polygon export accepts an existing single-band probability GeoTIFF; it does not run
inference. See `docs/SETUP.md` for the command and `docs/VALIDATION_REPORT.md` for tested limits.
Pull requests run locked Python tests and Ruff on Ubuntu and Windows through `.github/workflows/ci.yml`.

## Data licence and attribution

Ground truth: Manske, D. (2026). *Geo-locations and System Data of Renewable Energy Installations in Germany* (V20260203). Zenodo. https://doi.org/10.5281/zenodo.20716459. Source: BNetzA Marktstammdatenregister. Licence: dl-de/by-2-0. Derived label files keep attribution.
