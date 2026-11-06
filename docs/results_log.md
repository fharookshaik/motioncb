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
