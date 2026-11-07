# Results log (append-only)

One entry per finished arm or audit. Numbers only, with their CI; interpretation belongs in the paper.

Format:
```
## <date> | <arm_id> | label v1 | split s1 | reference r1
- seeds: 0,1,2 | GPU-h: x.x
- Δ object F1 (≥1 ha): +x.x [CI a, b] | Δ IoU: +x.x [CI a, b] | Holm-adjusted p: 0.xx
- recall by size bin: ...
- note: <one line>
```

## 2026-11-05 | M0.2 GPU probe
- GPU: RTX 2000 Ada Generation Laptop GPU; VRAM: 8,585,216,000 bytes; bf16 supported.
- Synthetic U-Net ResNet-50 training step, 10 bands, 256 px, bf16, AdamW: batch 16 fits (cap 16); peak allocated 1,809,407,488 bytes.
- Random encoder weights; synthetic data; no claims about full training throughput.

## 2026-11-06 | M1.3 completeness audit | label v1 | split s1
- windows: 60 (15 per region), one per block; each centred on a positive German label in a val/test block; seed 20261106
- labelled positives fully inside windows: 138; missed farms inside windows: 2 (W18, W34)
- omission rate: 1.43% (2 / 140); block-bootstrap 95% CI [0.00%, 3.62%] (10,000 resamples over 60 blocks)
- note: windows are anchored on labelled farms, so this is omission near labelled farms, not landscape-wide omission. W40 lists 2 farms outside its window; excluded from the count.

## 2026-11-06 | M1.5 preparation only | label v1
- Exported 100 sampled outlines and a blank review form to `runs/audit_m1_5/`; seed 20261106.
- Verified polygon/form/manifest ID alignment and source-label SHA-256; no QGIS project generated.
- No scientific result yet: Fharook's visual review and decision-log acceptance paragraph are pending.

## 2026-11-06 | M1.5 source-documentation closure | label v1
- Supersedes the pending manual-review status above: visual review waived; source-backed semantics paragraph recorded in `docs/decisions.md`.
- Sample remains unreviewed; no observed category counts, error rates or independent validation results.
- Intended convention: panel-array footprint per Manske et al. (2022), §3.2, cited by V20260203; current-release adherence not independently audited.

## 2026-11-06 | M1.5 cleanup | label v1
- Obsolete manual-review tooling and generated files removed at Fharook's request; source-backed closure retained.
- Correction to the blanket unreviewed status above: three partial `panel_rows` entries existed in the CSV; IDs preserved in `docs/decisions.md` before removal. No completed audit or release-wide validation claimed.

## 2026-11-06 | M1.6 test-set build | label v1 | split s1
- T-new (V20260203 vs V20240104 substitute, geometric match IoU 0.5 and 50 m): 2,131 new polygons; 876 label-v1 positives; 178 in test blocks; 173 kept.
- T-new sensitivity: IoU 0.3, 0.5, 0.7 at 50 m all give 173; at IoU 0.5, 25, 50, 100 m give 178, 173, 169.
- T-new commissioning: 140 of 173 by `commission_last` in 2024.
- T-indep (KIT RADAR manual labels, CC BY-SA 4.0): 15 of 84 tiles usable (11 NRW, 4 Hesse); 1,759,716 ground-PV pixels (about 7.0 ha); six label-v1 positives touch usable tiles, none commissioned after the tile year.
- note: data-only result. No model, no test-split metric, no `make eval-test`, so `runs/test_access.log` is not written.

## 2026-11-07 | M0/M1 hardening verification | label v1 | split s1
- `make audit-summary`: 60 windows/unique original blocks, 138 fully-contained positives, 2 in-window misses; 2/140 = 1.428571%; 95% CI [0, 3.623188%], 10,000 whole-window/block bootstrap resamples, RNG seed 20261106. Conditional label-anchored omission only; denominator/exclusion approval remains pending Fharook.
- Audit input SHA-256: windows `1ead27f4ffaaaba1fca83c184b7e6e6790a8c8e22c5a83216b859fa672262c5b`; form `9d2c32405196454ecc5fff6c78cf87117e61b0bf10f474064e545fd0b577a379`; labels `d0717aa76067d6d2d788a16e78262c7814060783954d81da839f50810d019b45`.
- Current s1 hashes unchanged: blocks `db9d3b50ba3fcf6d4ed5447159d7fdca41a98f8aa1210a465f8cc8f913b03b40`; polygons `cb41f8961f037896e8b0d2da381d2b5ac8abbf10e23d93523bd9a6aba18bfda7`; report `063c3ccb7dd9f69d6a252c100c8a2b521618653e415d72c01fdc22bb250a1b43`.
- Read-only archive check: all retained audit windows fit their original quadrant blocks and original val/test attributes match; one window per block. No redraw or artifact rebuild. Historical test-set reports remain historical; new provenance fields apply on future builds.
- Checks: 30 tests pass; ruff covers source, tests and scripts; disk within budget. Rasterio CRS/reprojection smoke test passes with deliberately invalid inherited PostGIS settings. Leakage-auditor found no concrete leakage introduced; results-reviewer checked audit-summary calculation.
