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
- 2026-11-05 | Use Python 3.11 with uv and PyTorch 2.9.1 CUDA 12.8 wheels on native Windows | GPU-enabled locked environment; driver 596.71 | Claude Code
- 2026-11-06 | Do not change the reference negative-sampling ratio or generate a chip manifest yet: `reference.yaml` specifies 1:1, while the roadmap specifies a 1:3 parent pool with a nested 1:1 subset | The subset/manifest semantics are not defined well enough to infer intent; researcher clarification is required before freezing data | Codex (audit)
- 2026-11-06 | Prepare only bounded, draft nested candidate profiles; do not freeze a reference manifest or start training | Real source labels are available; 1:1 versus 1:3 scientific intent still needs confirmation | Codex (engineering)
- 2026-11-06 | Preserve label v1 parsing, including 25 year-only commissioning strings treated as missing; report date precision explicitly rather than imputing dates | Real archive validation reproduced the documented 9,219 positive / 1,765 ignore labels | Codex (validation)
- 2026-11-06 | Preserve the first local split outputs and verify further runs in memory; local reproduction is provisional (2.01% deviation, 128 crossing polygons versus documented 2.2%/130) | Original historical split artifacts are absent; equality to the historical freeze cannot be established | Codex (validation)
- 2026-11-06 | Record country-boundary diagnostics separately from unchanged v1 latitude flags | GISCO 2024 1:1M identifies five Danish centroids, including 10422 and 10469 missed by the latitude proxy; geographic protocol requires review | Codex (validation)
- 2026-11-06 | Keep one public Collection-1 Sentinel-2 scene in a separate exploratory QA manifest with reference_compliant=false | It validates actual grid/label alignment; single-scene SCL+Sen2Cor probability does not fulfill the reference seasonal/cloud-mask protocol | Codex (engineering)
