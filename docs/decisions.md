# Decision log (append-only, newest at the bottom)

Format: `YYYY-MM-DD | decision | reason | who`

- 2026-11-03 | Ground truth = UFZ/MaStR release V20260203 (Zenodo 10.5281/zenodo.20716459), solar polygons + records | Site-verified national PV polygons | fharook
- 2026-11-03 | Hardware: 1× 8 GB NVIDIA GPU, 32 GB RAM, 500 GB disk. GFMs that do not fit run frozen only; compute budget ≈300 GPU-h Tier 1 | Available workstation | fharook
- 2026-11-03 | Polygons located outside Germany are KEPT (flagged `outside_germany_flag`). Measured: 3 polygons (area_id 10405, 10416, 10435), all in Denmark; the initial audit reported 2 because it used a 55.1° latitude cut-off, which missed Bornholm (55.06°N) | fharook's instruction ("can be included") | fharook
- 2026-11-03 | No DOP orthophotos as model input or for the resolution sweep: not freely available for all Länder and often outdated. The resolution axis uses HLS 30 m, S2 10 m and optionally S2 super-resolution | Data availability | fharook
- 2026-11-03 | Visual audits (completeness, semantics, false positives) use freely viewable high-res basemaps for inspection only, never as model input or redistributed figures | Replaces DOP for auditing | Claude (proposed)
- 2026-11-03 | Label v1: imagery window Apr–Sep 2025, 3-month commissioning buffer → polygons with any record commissioned ≥ 2025-01-01 are ignored; area_accuracy 2 and unlinked are ignored | Temporal alignment of labels and imagery | Claude (per study design)
- 2026-11-03 | Split s1: 20 km EPSG:3035 blocks, 70/10/20, greedy balance stratified by a 4-region proxy (lon 10.5°, lat 51.0°), seed 20261103; worst deviation 2.2% | Spatial leakage control | Claude (per study design)
- 2026-11-03 | Journal undecided; keep all outputs venue-neutral | fharook will decide later | fharook
- 2026-11-03 | Imagery backend proposal: Google Earth Engine server-side compositing, STAC as fallback; final choice after the M2.1 benchmark | Local disk and bandwidth limits | Claude (proposed)
