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

## 2026-11-06 | source-validation audit | label v1 | provisional local split s1

- Source census: 10,984 polygons; 14,250 records; 9,219 positive / 1,765 ignored; positive area 33,648.5 ha.
- Geometry errors / duplicate polygon IDs: 0 / 0. Parsed missing commissioning dates: 39, including 25 year-only strings.
- Local split PV area shares: train 69.9957%, validation 10.0029%, test 20.0014%; worst balance deviation 2.01%; crossing polygons 128.
- These are deterministic census/validation counts, so sampling CIs do not apply. No model benchmark was run.
- Evidence: `data/interim/raw_validation.json`, `data/processed/split_verification.json`; historical split artifacts unavailable, local freeze not approved.
