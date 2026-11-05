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
