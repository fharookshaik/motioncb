"""Imagery acquisition and compositing (ROADMAP M2).

Contract: given a chip/block manifest and an imagery spec from the resolved config
(sensor, bands, composite, window, cloud mask), write one GeoTIFF/Zarr per chip in its
native UTM grid, uint16 reflectance x10000 (S2/HLS) or float16 dB (S1), nodata documented.
Backends: gee.py (server-side compositing via computePixels) and stac.py (odc-stac windows).
Must be resumable and idempotent; never keep raw scenes.
"""
