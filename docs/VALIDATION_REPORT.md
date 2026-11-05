# Validation report

Validation date: 2026-11-06. Host: macOS arm64, Python 3.11.15 managed by `uv`.

## Commands and results

| Command | Result | Scope |
| --- | --- | --- |
| `UV_CACHE_DIR=/tmp/uv-motioncb uv sync --extra dev --extra geo` | Passed | Locked core, dev, and GIS dependency install; torch/training and provider extras omitted. |
| `UV_CACHE_DIR=/tmp/uv-motioncb uv run pytest -q` | 8 passed, 2 skipped | Synthetic labels/splits, pixel metrics, and probability raster export. Skips require derived real labels/splits. |
| `UV_CACHE_DIR=/tmp/uv-motioncb uv run ruff check src tests` | Passed | Python package and tests. |
| `uv run python -c "import geopandas, rasterio, torch; ..."` | Failed: `torch` missing | Torch is in the optional training extra and was not installed on this host. |
| `nvidia-smi` | Unavailable | No NVIDIA tooling/device on this Apple Silicon machine. |
| `make test` | Not runnable here | Makefile invokes `powershell.exe`, unavailable on macOS; equivalent `uv run pytest -q` was run. |

`.github/workflows/ci.yml` now runs the locked test and Ruff checks on Ubuntu and Windows for pushes
to `main` and pull requests. The workflow itself has not yet run on GitHub.

## Acceptance status

| Status | Evidence |
| --- | --- |
| **IMPLEMENTED** | Label curation, spatial split assignment, accumulated ignore-aware pixel metrics, and single-band probability-raster polygonization are present. |
| **TESTED WITH SYNTHETIC DATA** | 8 tests pass, covering label handling, split balancing, hand-computed pixel metrics, probability components, nodata exclusion, WGS84 output, and invalid raster inputs. |
| **VALIDATED WITH REAL DATA** | None. The checkout contains no raw source release, generated split, satellite imagery, checkpoint, or model output. |
| **BLOCKED** | Real label/split validation, composite ingestion, reference training/checkpoint, real inference, and performance profiling need data, provider access, and the CUDA workstation. |
| **NOT IMPLEMENTED** | FastAPI API, durable inference worker, Next.js/MapLibre frontend, model/training pipeline, guarded metrics suite, GIS package integration tests, CI workflow. |

The raster vectorizer tests validate only synthetic projected GeoTIFFs. They do not validate model
quality, production-area throughput, Cloud Optimized GeoTIFF behavior, or real-world GIS consumer
compatibility. No scientific metrics are reported or appended to `docs/results_log.md`.

## Known issues / next validation

- Resolve the 1:1 versus 1:3 negative-sampling definition before creating a chip manifest.
- Review the region proxy and verify real split assignments before the split freeze.
- Replace or constrain the latitude-only `outside_germany_flag` before relying on it as a country
  boundary classification.
- Run integration checks against V20260203 and actual Sentinel-2 artifacts, then validate on one
  representative study area and inspect GeoJSON/GeoTIFF outputs in a GIS client.
