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
