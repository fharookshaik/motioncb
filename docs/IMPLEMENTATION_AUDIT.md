# Implementation audit

Audit date: 2026-11-06\
Repository: `fharookshaik/motioncb`, branch `feat/motioncb-end-to-end-v1`, starting commit `5d09c11`\
Host: macOS arm64, Python 3.11.15 via `uv`; no NVIDIA GPU

## Existing architecture and implementation status

The repository is a small Python research package in `src/solarde/`. It currently contains YAML
configuration loading, label curation (`labels/curate.py`), and spatial-block split assignment
(`splits/blocks.py`). The repo also includes the study design, roadmap, decision/result logs, label,
split, reference-model and ablation configs, a locked Python environment, and two synthetic plus two
data-conditional integration tests. There is no application API, frontend, inference service, model
implementation, imagery ingestion, chip sampler, training runner, evaluation suite, export path, or
CI workflow. `data/` has only `data/processed/.gitkeep` in this checkout.

| Area | Status | Evidence |
| --- | --- | --- |
| Label v1 curation | Implemented; synthetic behavior tested; real release not present | `src/solarde/labels/curate.py`, `tests/test_labels_and_splits.py` |
| Spatial s1 split creation | Implemented; balance primitive tested; real assignments not present | `src/solarde/splits/blocks.py`, `configs/splits.yaml` |
| Data provenance/config | Partially implemented | YAML and label report hashes exist; no chip/model manifests or run registry |
| Imagery, chips, models, training | Not implemented | package directories are empty `__init__.py` files |
| Evaluation and test guard | Not implemented | package directory is empty; no `runs/test_access.log` |
| API, jobs, web map, GIS exports | Not implemented | no `apps/` or frontend tree |
| CI and cross-platform setup | Not implemented / inconsistent | no workflow; Makefile hardcodes PowerShell |

## Test and environment results

- Initial `git status`: clean on `main`; `origin` points to the supplied GitHub repository; recent
  history was `5d09c11` and `59f5682`. A dedicated implementation branch was created before edits.
- `uv sync --extra dev --extra geo` completed successfully using Python 3.11.15 and the repository
  lockfile. This installed the test, lint, and geospatial stack. Training and imagery extras were
  not installed.
- `UV_CACHE_DIR=/tmp/uv-motioncb uv run pytest -q`: **3 passed, 2 skipped** in 12.63 s. The two
  skipped tests require generated labels/splits and raw source data.
- `UV_CACHE_DIR=/tmp/uv-motioncb uv run ruff check src tests`: **failed with 4 findings**: three
  redundant integer casts and one `datetime.UTC` modernization in label/split reporting.
- `UV_CACHE_DIR=/tmp/uv-motioncb uv run python -c "import geopandas, rasterio, torch; ..."`:
  geospatial packages import, but the command fails because PyTorch is not installed in the current
  environment. No CUDA probe is possible: this is an Apple Silicon host and `nvidia-smi` is absent.
- `make test` cannot use this host's shell: the Makefile sets `powershell.exe`, which is unavailable
  on this macOS environment. The equivalent locked-environment pytest command above works.
- Raw V20260203/V20250101 data, prepared split files, Sentinel imagery, pretrained weights, and
  external GEE/Copernicus credentials are absent. No real-data or real-inference claim can be made.

## Confirmed defects and inconsistencies

1. **Sampling ratio conflict remains unresolved.** `configs/experiment/reference.yaml` sets
   `chips.neg_ratio: 1.0`; `docs/ROADMAP.md` and `CLAUDE.md` describe 1:3 negatives with a nested
   1:1 subset, and the registry includes `H_neg3`. The repository does not define the manifest
   names/subset nesting well enough to infer whether 1:3 is an acquisition pool and 1:1 is the
   reference manifest, or whether the reference itself is meant to change. Do not freeze a sampler
   or benchmark until this is resolved and recorded.
2. **Cross-platform Makefile is Windows-only.** All documented `make` targets invoke
   `powershell.exe`, despite the stated practical goal of local macOS/Linux development.
3. **Lint currently fails** on four straightforward findings in label/split report construction.
4. `outside_germany_flag` is computed from a latitude threshold (`lat > 55.06`), so it is a
   northern-latitude proxy rather than a Germany-border test. It may falsely flag German features
   north of that line and miss other border cases; the known three Danish records should be checked
   against an actual boundary before the flag is used as a geographic truth claim.
5. The split code computes and reports cross-split polygons, but it does not create the required
   2,560 m border exclusion, raster masks, or chip-level provenance. The code comment delegates
   these safeguards to a future sampler that does not exist yet.
6. `docs/study_design.md` calls 20 m Sentinel-2 bands “resampled to 10 m (bilinear)”. No imagery
   path exists to confirm CRS alignment, resampling, masks, or radiometric handling.

## Scientific risks and open decisions

- The region assignment uses longitude/latitude thresholds rather than the Länder grouping that
  roadmap item M1.4 says must be reviewed before split freeze. Since actual split files are absent,
  impact on assignments has not been measured.
- The configured split seed and parameters do not establish that a split has been created in this
  environment. The reported 909 PV blocks, 130 crossing polygons and 2.2% balance are documentary
  figures only here.
- No imagery-to-label alignment, cloud/nodata behavior, train-only normalization, mask handling,
  object metrics, test-access guard, or seed/config immutability can yet be verified.
- The 1:1 versus 1:3 sampling definition is a scientific reproducibility blocker; preserve both
  source statements until the responsible researcher resolves the intended reference and nested
  experimental subsets.
- No model weights are present and the current host has no CUDA device. Training, GPU memory
  feasibility, and real inference are blocked by external data/model/hardware availability.

## Missing dependencies, credentials, and external resources

- Base/dev/geo dependencies are installed in the local `.venv`; torch, Lightning, training/model
  libraries, and Earth Engine/STAC integrations are not installed.
- Raw UFZ/MaStR release V20260203, earlier release V20250101, KIT RADAR labels, and imagery are not
  available in the checkout.
- No Google Earth Engine project/authentication or Copernicus Data Space credentials are configured.
- No supported NVIDIA CUDA workstation is available on this host.

## Safe reuse

- Keep the label curation and split assignment modules as the research core; their small synthetic
  tests pass. Preserve the label v1, ignore value 255, spatial CRS, reference YAML, and decision log.
- Reuse `load_yaml`/`resolve` for CLI config paths and the existing src layout.
- Do not infer scientific corrections from missing data, and do not write synthetic metrics into
  the results log.

## Proposed target architecture

- Keep dataset, imagery, model, training, inference, evaluation and analysis behavior inside
  `solarde` modules with typed, reusable functions.
- Add a thin FastAPI/Pydantic layer under `apps/api/` that calls those services and returns truthful
  artifact and job status. Long jobs need persisted state and resumable execution outside an
  in-process request/background task.
- Add a separate Next.js/TypeScript/MapLibre client that displays only supported regions and
  georeferenced prediction artifacts actually produced by the scientific core.
- Keep filesystem-backed versioned manifests/artifacts for the pilot; add MLflow when training
  dependencies and the first reproducible run are available. Do not introduce a database or
  distributed infrastructure before the pilot demonstrates the need.

## Short implementation checklist

1. Resolve the sampling protocol and review provisional region assignment before freezing splits.
2. Make development commands portable and clear the lint findings; preserve the existing tests.
3. Validate raw labels and real split outputs when the source release is available.
4. Implement imagery/chip manifests and ignore-aware rasterization, then verify alignment on one
   representative real study area.
5. Implement reference model/training and validation-only selection on the supported GPU host.
6. Implement guarded metrics, resumable inference jobs, API, map display, and GIS exports on real
   output artifacts; run acceptance checks and document evidence.

## Blockers requiring external resources

- Raw ground-truth releases and independent validation labels are required for real data validation.
- Satellite access/credentials or an approved public STAC path are required for the reference
  composite and wall-to-wall study-area imagery.
- SSL4EO-S12 weights and an NVIDIA GPU host are required to validate the reference checkpoint and
  measure model/training performance.
- The researcher must resolve the 1:1 versus 1:3 reference and acquisition/subset definitions and
  complete visual audits identified by `[H]` items in the roadmap.
