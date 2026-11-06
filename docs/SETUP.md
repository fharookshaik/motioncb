# Local setup

## Requirements

- Python 3.11 and `uv`.
- Git and a GIS-capable Python environment. The current development/test install supports macOS,
  Linux, and Windows; GPU training is intended for the documented NVIDIA CUDA workstation.
- Raw UFZ/MaStR data and imagery are not included in Git. External acquisition access is needed for
  real-data processing.

## Install the current core

Run from the repository root:

```sh
uv sync --extra dev --extra geo
uv run pytest -q
uv run ruff check src tests
```

These commands use `uv run` from PowerShell as well as macOS/Linux shells. The Makefile currently
uses PowerShell syntax and is Windows-specific; use direct commands above on other hosts.

## Add training or imagery dependencies

```sh
uv sync --extra dev --extra geo --extra train
```

On the intended Windows training workstation, inspect the driver and device before a run:

```powershell
nvidia-smi
uv run python -c "import torch; print(torch.__version__, torch.cuda.is_available())"
```

The current macOS host has no CUDA device. The repository has not validated the locked training
stack against its target 8 GB NVIDIA workstation.

The public bounded STAC preview needs only the core/dev/GIS install above. Optional Earth Engine
and other provider dependencies are available through `uv sync --extra imagery`; configure their
credentials outside the repository and never commit tokens.

## Current commands

```sh
uv run python -m solarde.data.raw --config configs/data.yaml --archive /Users/likhithreddy/Downloads/V20260203.zip
uv run python -m solarde.labels.curate --config configs/data.yaml
uv run python -m solarde.splits.blocks --config configs/splits.yaml --data-config configs/data.yaml
uv run python -m solarde.splits.verify --config configs/splits.yaml --rebuild-check
uv run python -m solarde.data.chips --config configs/preparation.yaml
uv run python -m solarde.imagery.preview --config configs/preparation.yaml
uv run python -m solarde.evaluate.vectorize --input path/to/probabilities.tif --output path/to/predictions.geojson --config configs/experiment/reference.yaml
```

Replace the archive argument with its existing local path. Import verifies CRC/checksums, extracts
only the configured GPKG/CSV, reuses identical files, and rejects conflicting files. The ZIP stays
at its original path. Raw and generated data are ignored by Git.

Run label/split creation only for initial setup. The split CLI refuses to overwrite any existing
artifact; use verification thereafter. `--rebuild-check` reconstructs assignments in memory only.
Optional `--germany-boundary` / `--denmark-boundary` arguments accept local authoritative boundary
files. They add diagnostics without changing source labels.

`configs/preparation.yaml` creates a bounded train-only pilot plan and masks. Repeating preparation
verifies checksums and reuses outputs; changed code/config/data requires a new output directory.
Its candidate sampling profiles are draft conventions, not a frozen benchmark protocol.

The preview downloads only one scene's chip windows and saves its ten bands, validity/mask rasters,
PNG overlay, source metadata, and checksums under `data/processed/pilot_preparation/preview/`.
It is exploratory single-scene QA, not the approved seasonal reference composite. Completed outputs
are reused after checksum verification; interrupted metadata queries are tied to the requested
area, date window, collection, and cloud filter. No training is started.

For separate test results use `uv run pytest -q -m integration` and
`uv run pytest -q -m 'not integration'`. The vectorization command requires an existing single-band
probability GeoTIFF; it does not generate model predictions.

There is no API or frontend startup command yet. See [API](API.md) and
[Validation report](VALIDATION_REPORT.md) for current status and limits.
