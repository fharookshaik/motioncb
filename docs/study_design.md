# Study design: ablation study of large-scale PV farm detection and segmentation in Germany

Canonical in-repo copy (v2, 2026-11-03). A shared Claude doc carries the same content for
reading and commenting. If they differ, this file plus `docs/decisions.md` win.

## 1. Research questions

1. **RQ1 Sensor and resolution.** How do detection and delineation scale with ground sampling distance
   (S2-SR 2.5 m (optional), S2 10 m, HLS 30 m)? Does SAR add anything? What is the smallest reliably
   detected farm per sensor, in hectares?
2. **RQ2 Spectral content.** Which S2 band groups carry the signal (visible, red-edge, NIR, SWIR)?
3. **RQ3 Temporal context.** Does multi-temporal input beat a single Apr–Sep median composite?
4. **RQ4 Model and pretraining.** Do geospatial foundation models beat an EO-pretrained CNN at equal
   tuning budget on an 8 GB GPU, and at what compute cost?
5. **RQ5 Labels and data volume.** How sensitive are results to label definition and training-set size?
6. **RQ6 Generalisation.** How well do the best configurations transfer across regions, to new
   builds, and to independent labels?

## 2. Ground truth (measured on V20260203)

- 10,984 MultiPolygons, 41,823 ha. Median 1.66 ha. ≥1 ha: 6,796 polygons (61.9%) hold 94.8% of
  the area. Under 1 ha: 38% of polygons, 5% of the area.
- Width (short side of the rotated bounding box): median 93 m; 17.7% < 50 m; 4.7% < 20 m.
- area_accuracy 2: 661. Unlinked (area_related 0): 384. Polygons with a record commissioned
  2025–2026: 1,257. Multi-phase: 485.
- Subtypes: agrivoltaics 153, car parks 48, floating 39; plus 717 east-west, 137 tracked and 19
  vertical arrays.
- Median distance to the nearest neighbouring farm: 627 m (46.7% within 500 m), so splits must be
  spatial blocks.
- 3 polygons lie in Denmark (area_id 10405, 10416, 10435): **kept**, flagged.
- Earlier release V20250101: 9,770 polygons. The difference gives test set T-new.

## 3. Label protocol (label v1, `configs/data.yaml`)

Positive = record-linked, area_accuracy 1, every record commissioned before 2025-01-01 (the Apr–Sep
2025 window minus a 3-month buffer), none decommissioned before 2025-09-30. Everything else is
**ignore** (255): excluded from the loss and the metrics. Nothing is deleted.
Result: 9,219 positive (33,649 ha; 5,766 ≥1 ha) and 1,765 ignore.

Rooftop PV is not labelled: the task is ground-mounted PV. A completeness audit (60 windows of
5×5 km, visual inspection on freely viewable high-res basemaps, used for inspection only)
estimates the label omission rate, which caps achievable precision.

## 4. Imagery (no DOP)

| Source | GSD | Role |
| --- | --- | --- |
| Sentinel-2 L2A, 10 bands, median Apr–Sep 2025, Cloud Score+ / SCL masking | 10 m | Reference |
| Sentinel-1 GRD VV/VH, median + SD, dB | 10 m | A: SAR alone and fused |
| HLS L30/S30 | 30 m | A: coarse optical, harmonised with S2 |
| S2 super-resolved ×4 (one open model) | 2.5 m | A: optional (Tier 3), positive-chip subset |
| S2 single scene / four seasonal medians / monthly | 10 m | C: temporal |

Compositing happens on the server (Google Earth Engine) or via streamed STAC windows. Raw scenes are
never stored. Chips are 256 px in their native UTM grid.

## 5. Reference configuration (`configs/experiment/reference.yaml`)

U-Net + ResNet-50 (SSL4EO-S12 MoCo, all S2 bands), BCE+Dice, AdamW + cosine, fixed step budget,
bf16, auto batch ≤16 with accumulation to 16, flips/rot90/mild brightness, threshold 0.5,
checkpoint chosen by val object-F1 (≥1 ha). Every arm gets the same HPO sweep (3 LR × 2 WD).

## 6. Ablation axes (`configs/ablations/registry.yaml`)

| ID | Tier | Arms |
| --- | --- | --- |
| A Sensor | 1 | HLS 30 m; S1 only; S1+S2 early fusion; S1+S2 mid-fusion; (S2-SR 2.5 m, tier 3) |
| B Bands | 1 | RGB; RGB+NIR; RGB+red-edge; RGB+SWIR; all+indices; drop VIS / red-edge / NIR / SWIR |
| C Temporal | 1/2 | single scene; four seasonal medians; (monthly series with U-TAE, tier 2) |
| D Architecture | 2 | DeepLabv3+; HRNet-W18; SegFormer-B2 |
| E Initialisation | 1 | random; ImageNet; GFMs frozen (Prithvi-EO-2.0-300M, TerraMind-B, DOFA-B, Satlas-SwinB, Clay); top-2 GFMs fine-tuned if they fit in 8 GB |
| F Labels | 1 | area_accuracy 2 as positive; unlinked as positive; no temporal filter; soft labels; 1 px boundary ignore; train only ≥1 ha |
| G Data fraction | 1 | 5 / 10 / 25 / 50% × {SSL4EO CNN, best GFM} |
| H Loss and sampling | 2 | BCE; Dice; Focal+Dice; Lovász; negatives 1:3; hard negatives |
| I Context | 2 | 128 px; 512 px |
| J Post-processing | 1 | threshold sweep; morphology; 0.1 ha minimum area; D4 TTA (no retraining) |

Factorials: resolution × initialisation; data fraction × initialisation.
Budget (pre-pilot estimate, 8 GB GPU): Tier 1 ≈ 37 arms × 3 seeds ≈ 300 GPU-h; Tier 2 ≈ 90 GPU-h.

## 7. Splits and evaluation

- Split s1: 20 km EPSG:3035 blocks, 70/10/20, balanced on PV area and size mix within 4 VG250 Land groups
  (North, West, South, East; worst deviation 1.8%). A 2.56 km border buffer. 132 polygons that cross a split border are masked outside
  their own block. 5-fold block CV is used for the final check only.
- Test sets: T-main (held-out blocks), T-region (leave-one-region-out), T-new (V20260203 minus
  V20250101), T-indep (KIT RADAR manual labels, Hesse/NRW), T-wall (false positives per 1,000 km²).
- Primary endpoints: object F1 for farms ≥1 ha (detected = ≥10% covered) and accumulated PV IoU.
  Secondary: recall per size bin and mounting type, delineation rate (IoU ≥0.5), boundary F1 (1 px),
  area error, false positives per 1,000 km², cost.

## 8. Statistics

3 seeds (5 when |Δ| < 2× seed SD). 95% CIs from a block bootstrap (2,000 resamples). Paired Δ vs the
reference. Holm correction per axis. Pre-declared minimum effects (set after the pilot; draft:
ΔIoU ≥ 1.0, Δ object F1 ≥ 1.5 points). Mixed model for the factorials. All runs reported.

## 9. Threats to validity

Unmapped farms (completeness audit plus a false-positive audit); label/imagery date mismatch
(temporal filter, F_no_temporal, T-new); spatial autocorrelation (blocks, buffer, T-region); regional
imbalance (stratified splits); S2 misregistration (boundary tolerance, F_boundary1px); polygon
semantics (author-documented panel-array footprint, Manske et al. 2022 §3.2; release-wide adherence
not independently audited); unequal tuning (equal sweep); GPU limits that force frozen GFMs (reported
explicitly as a limitation).

## 10. Sources

- Manske (2026), V20260203: https://zenodo.org/records/20716459 · V20250101: https://zenodo.org/records/16942382
- Manske et al. (2022), Data 7(9):128: https://doi.org/10.3390/data7090128
- KIT RADAR PV reference labels: https://b2find.eudat.eu/dataset/a788c3e6-6a4a-529e-97cc-92829fac155d
- GEO-Bench-2: https://arxiv.org/html/2511.15658v2 · Prithvi-EO-2.0: https://arxiv.org/html/2412.02732v3
- Mourabiti et al. (2026), SR for PV mapping: https://www.fortiss.org/forschung/ergebnisse/publikationen/details/generative-adversarial-synthetic-super-resolution-for-satellite-based-solar-panels-mapping
