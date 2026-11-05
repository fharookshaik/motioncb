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

Imagery extras are installed with `uv sync --extra imagery`; provider credentials must be configured
outside the repository. Never commit tokens. No credential template or acquisition command exists
yet.

## Current commands

```sh
uv run python -m solarde.labels.curate --config configs/data.yaml
uv run python -m solarde.splits.blocks --config configs/splits.yaml --data-config configs/data.yaml
uv run python -m solarde.evaluate.vectorize --input path/to/probabilities.tif --output path/to/predictions.geojson --config configs/experiment/reference.yaml
```

Label and split commands require the raw release and write derived files under `data/`. Do not
regenerate split s1 once training has started. The vectorization command requires an existing
single-band probability GeoTIFF; it does not generate model predictions.

There is no API or frontend startup command yet. See [API](API.md) and
[Validation report](VALIDATION_REPORT.md) for current status and limits.
