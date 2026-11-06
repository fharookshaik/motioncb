# Validation report

Validation date: 2026-11-06. Host: macOS arm64, Python 3.11.15 via `uv`.
The implementation audit remains the historical baseline; this report describes the latest actual run.

## Original archive and labels — VALIDATED WITH REAL DATA

- Original ZIP preserved at `/Users/likhithreddy/Downloads/V20260203.zip`; no second archive copy made.
- CRC checks passed for all 21 entries. Only the configured solar polygon GPKG and installation CSV
  were extracted. Repeated import reused both byte-identical files without rewriting them.
- Archive SHA256: `e9f583c5b19fa72e9e3d0ce18e7b8aaf6859d129b3f7fb0b821bfa10a84a5fc1`.
- GPKG: 10,984 MultiPolygons, EPSG:4326, zero missing/empty/invalid geometries, zero duplicate area IDs.
- CSV: 14,250 records, all linked to known polygons. 384 polygons have no installation record.
- Label v1: **9,219 positive / 1,765 ignored**; positive area 33,648.5 ha, 5,766 positive farms ≥1 ha.
- Ignore reasons (overlapping): accuracy 2 = 661; built after cutoff = 1,257; unlinked = 384;
  commissioning date missing = 39; decommissioned = 23.
- The 39 missing parsed commissioning dates include **25 year-only strings** and 14 missing values.
  Existing v1 handling is preserved; no dates were imputed and no label rule changed.
- Full machine-readable evidence, source hashes, and reuse status: `data/interim/raw_validation.json`
  and `data/interim/labels_v1_report.json`. Raw/derived datasets remain Git-ignored.

## Geographic splits — VALIDATED LOCALLY; NOT A HISTORICAL FREEZE VERIFICATION

No split artifacts or training runs existed in this checkout before this run. The first local
creation used unchanged configured parameters. Subsequent verification rebuilt assignments in
memory and confirmed identical values without rewriting any split artifact.

- 20 km EPSG:3035 grid: 2,360 blocks, 909 with positive PV; 10,984 unique polygon assignments.
- PV area shares: train 69.9957%, validation 10.0029%, test 20.0014%.
- Worst relative balance deviation: **2.01%**; cross-split polygons: **128**. Historical documentation
  states 2.2% and 130; the original artifacts are unavailable, so equality to that historical split
  cannot be established. Local outputs are preserved and must not be treated as an approved freeze.
- Stable block IDs, centroid ownership, crossing flags, and regional shares passed verification.
- The regional longitude/latitude proxy remains provisional; no Länder grouping was substituted.
- [Eurostat GISCO NUTS 2024 boundaries](https://ec.europa.eu/eurostat/web/gisco/geodata/statistical-units/territorial-units-statistics)
  at 1:1 million identify Danish centroids **10405, 10416, 10422, 10435, 10469**. The v1 latitude flag
  identifies only 10405, 10416, 10435. Another centroid, 10921, lies outside the generalized Germany
  boundary and is already ignored as unlinked. Country geometry results are diagnostic at this
  scale; source labels and latitude fields were not changed.
- Evidence: `data/processed/split_verification.json`; boundary URLs/hashes:
  `data/raw/boundaries/sources.json`.

## Pilot preparation — IMPLEMENTED AND VALIDATED WITH REAL LABELS

- Pilot farm **area_id 10130**, 9.9953 ha, centroid 10.851235°E, 48.150195°N, selected from train.
- **16 masks**: 4 positive and 12 candidate negatives, all 256×256 pixels at 10 m in EPSG:32632.
- Whole chip footprints enforce the 2,560 m exclusion from any other split. Independent review
  measured a minimum distance of 11,330.77 m among the selected footprints.
- Draft 1:1 negatives are deterministically nested inside the 1:3 pool. Neither profile is approved
  or frozen. Land-cover stratification and training-only normalization remain unavailable.
- Ignore priority, nodata masking, cross-split polygon clipping, and fractional rasterization passed
  synthetic tests. The selected real mask examples do not include cross-split/ignored polygons.
- Source/config/data hashes bind the plan; output checksums verify reuse. Existing split creation is
  protected from overwrites; failed balance acceptance writes no split artifacts.
- Evidence: `data/processed/pilot_preparation/manifest.json`, `footprints.geojson`, and `*_mask.tif`.

## Satellite alignment QA — VALIDATED WITH ONE REAL SCENE

The public [Earth Search Collection-1 provider](https://github.com/Element84/earth-search/blob/main/docs/collections/sentinel-2-l2a.md)
provided bounded COG reads without credentials or retained complete scenes.

- Scene: `S2A_T32UPU_20250404T101510_L2A`, 2025-04-04, within the requested season.
- One ten-band chip, in configured order, resampled onto the exact prepared EPSG:32632 grid.
  Reflectance uses explicit asset scale 0.0001 and offset −0.1; 20 m bands use bilinear resampling.
- SCL/cloud probabilities use nearest resampling. Zero cloud probability is retained as clear sky;
  final validity also requires SCL vegetation/nonvegetated/water and cloud probability ≤40%.
- **98.9258% valid pixels**, **1,306 valid PV pixels**. Image, label, and validity rasters share
  exactly equal CRS, transform, and dimensions. The RGB/label overlay was visually inspected.
- Actual acquisition plus QA time: **40.23 seconds for one chip**. This is not the roadmap's 50-chip
  backend comparison or a seasonal-composite throughput benchmark.
- Evidence: `data/processed/pilot_preparation/preview/{image,mask,valid}.tif`, `qa.png`, `manifest.json`.
  Original acquisition-code hash is retained; a later query-cache safety fix was validated without
  downloading the completed image windows again.
- **Not reference training data:** this is a single scene with SCL + Sen2Cor probability, not the
  required seasonal median and approved Cloud Score+/s2cloudless path. Its manifest explicitly
  records `reference_compliant: false`; the preparation manifest still awaits imagery/protocol.

## Checks

```sh
uv run pytest -q -m 'not integration'
uv run pytest -q -m integration
uv run ruff check src tests
```

Current results: **18 unit/synthetic tests passed; 6 real-data integration tests passed; Ruff passed**.
`uv lock --check --offline` passed. Repeat preparation/preview reused all completed artifacts and
verified the unchanged original archive checksum. Local `data/` occupies 29.47 MB including the
preserved initial draft. Free disk is **12.6 GB**, below the project's 50 GB reserve; restore that
reserve before expanding acquisition beyond this bounded pilot.
All real-data tests ran locally. Data-dependent tests may skip on CI where the data is absent.
Independent leakage review found no leakage in the current draft artifacts. Its findings about
source-hash reuse, accepted-split gating, and interrupted STAC query-cache identity were fixed.

## Remaining work

The full Apr–Sep reference composite, approved cloud masking, land-cover-stratified negative pool,
train-only normalization/PyTorch dataset, complete split manifests, and scientific approval of the
sampling/geographic protocol remain unfinished. No reference training, checkpoint validation,
model inference, or benchmark result is claimed. No model metrics were added to the results log.
