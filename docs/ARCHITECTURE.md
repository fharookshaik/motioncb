# Architecture

## Current implementation

MotionCB currently has a Python package, `src/solarde/`, and configuration-driven research scripts.
Label curation and spatial block assignment are implemented. `solarde.evaluate.vectorize` converts a
single-band georeferenced probability raster into small-area GeoJSON candidate polygons. The
vectorizer uses the threshold and minimum-area settings in `configs/experiment/reference.yaml` by
default; benchmark callers must use the resolved frozen configuration explicitly.
`solarde.evaluate.pixel_metrics` accumulates confusion counts across windows, excludes ignore value
255, and computes pixel precision, recall, F1, and IoU from global counts rather than per-window
averages.

There is no API server, browser client, training code, imagery ingestion, inference runner, durable
job worker, or MLflow integration yet. The vectorizer is post-processing, not inference.
The Python test/lint CI workflow is configured for Ubuntu and Windows; no frontend or API contract
checks exist yet.

## Target boundaries

```text
Next.js + TypeScript + MapLibre (not implemented)
                    │ HTTP/GeoJSON
FastAPI + Pydantic API (not implemented)
                    │ reusable services
solarde: labels → splits → imagery → chips → models → train → evaluate → analysis
                    │ versioned manifests and artifacts
GeoTIFF/COG, GeoPackage, GeoJSON/GeoParquet, JSON; MLflow for experiments
```

Research logic belongs in `solarde`; API handlers should validate requests and call those reusable
services. The initial artifact store can remain filesystem-backed. Large inference jobs need
persisted state, resumable processing, explicit transitions, and a worker process that survives API
restarts. FastAPI in-process background tasks are unsuitable for long GPU jobs.

## Scientific data flow

1. Curate the V20260203 release to label v1 without deleting records; ignored records map to 255.
2. Assign labels to 20 km EPSG:3035 spatial blocks and freeze split s1 before training.
3. Build Sentinel-2 L2A composites and fixed chip manifests. Statistics are derived from train
   chips only; chips near other splits are excluded and cross-boundary polygons are masked.
4. Train the configured reference and ablations from immutable resolved configs and record code,
   data-manifest and seed provenance.
5. Select checkpoints and thresholds on validation only. The test set is guarded and logged.
6. Produce georeferenced probability rasters, vectorize them for browsing/export, and publish
   metrics with block-level uncertainty.

Stages 3–6 are still unimplemented except for the isolated raster-to-vector post-processing step.
The negative-sampling conflict and provisional region proxy need review before split/chip artifacts
are frozen.

## Storage and deployment direction

- Source label records: GeoPackage with source attribution and label version.
- Imagery and probabilities: GeoTIFF or Cloud Optimized GeoTIFF with CRS, transform, nodata, and
  manifest provenance.
- Small browser result sets: WGS84 GeoJSON. Larger derivatives: GeoParquet.
- Experiment records: immutable resolved YAML/JSON, run metadata, and MLflow once training exists.
- No database, Redis, Kubernetes, or deployment service is currently justified by a working pilot.
