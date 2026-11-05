"""Chip sampling, label rasterisation and the PyTorch DataModule (ROADMAP M3).

Contract: chips are 256 px at 10 m; masks use 1=PV, 0=background, 255=ignore; fractional
masks are float16 in [0,1]. Normalisation stats are computed from TRAIN chips only.
"""
