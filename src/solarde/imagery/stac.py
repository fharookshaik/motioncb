"""Small public Earth Search Collection-1 queries and streamed COG grid reads."""
from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.vrt import WarpedVRT

ENDPOINT = "https://earth-search.aws.element84.com/v1"
COLLECTION = "sentinel-2-c1-l2a"


def select_assets(item: dict, bands: list[str]) -> dict:
    """Select single-band reflectance assets, excluding visual RGB derivatives."""
    selected = {}
    for asset in item["assets"].values():
        spectral = asset.get("eo:bands", [])
        if len(spectral) != 1 or "reflectance" not in asset.get("roles", []):
            continue
        name = spectral[0].get("name")
        if name in bands:
            if name in selected:
                raise ValueError(f"Ambiguous reflectance asset for {name}")
            selected[name] = asset
    if missing := set(bands) - set(selected):
        raise ValueError(f"Missing required Sentinel-2 assets: {missing}")
    return selected


def get_json(url: str) -> dict:
    for attempt in range(3):
        try:
            with urlopen(url, timeout=60) as response:
                return json.load(response)
        except (HTTPError, URLError) as error:
            if isinstance(error, HTTPError) and error.code not in {429, 500, 502, 503, 504}:
                raise
            if attempt == 2:
                raise
            retry = getattr(error, "headers", {}).get("Retry-After", "0")
            time.sleep(min(10, max(2 ** attempt, int(retry) if str(retry).isdigit() else 0)))
    raise RuntimeError("Unreachable retry state")


def search(bbox: list[float], window: list[str], max_cloud: float = 20) -> list[dict]:
    """Follow all result pages, then filter tile cloud metadata; preserve item IDs."""
    params = {"collections": COLLECTION, "bbox": ",".join(map(str, bbox)),
              "datetime": f"{window[0]}T00:00:00Z/{window[1]}T23:59:59Z", "limit": 100}
    url = ENDPOINT + "/search?" + urlencode(params)
    items = {}
    pages = set()
    while url:
        if url in pages:
            raise ValueError("STAC pagination loop")
        pages.add(url)
        page = get_json(url)
        for item in page["features"]:
            if item["properties"].get("eo:cloud_cover", 100) <= max_cloud:
                items[item["id"]] = item
        next_link = next((link for link in page.get("links", []) if link["rel"] == "next"), None)
        if next_link and next_link.get("method", "GET") != "GET":
            raise ValueError("This bounded provider supports GET pagination only")
        url = next_link["href"] if next_link else None
    return sorted(items.values(), key=lambda item: (item["properties"]["eo:cloud_cover"], item["id"]))


def read_grid(asset: dict, *, crs, transform, shape: tuple[int, int], categorical: bool = False,
              zero_is_valid: bool = False) -> np.ndarray:
    """Read the target chip via a VRT; never download or retain a full scene."""
    with (
        rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY=3,
                     GDAL_HTTP_RETRY_DELAY=2, CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.TIF"),
        rasterio.open(asset["href"]) as source,
        WarpedVRT(source, crs=crs, transform=transform, width=shape[1], height=shape[0],
                  src_nodata=-9999 if zero_is_valid else asset.get(
                      "raster:bands", [{}])[0].get("nodata", source.nodata),
                  nodata=np.nan, dtype="float32",
                  resampling=Resampling.nearest if categorical else Resampling.bilinear) as vrt,
    ):
        return vrt.read(1, masked=True).filled(np.nan)


def reflectance(raw: np.ndarray, asset: dict) -> np.ndarray:
    """Apply explicit Collection-1 asset scale/offset; never guess missing metadata."""
    metadata = asset.get("raster:bands", [{}])[0]
    if "scale" not in metadata or "offset" not in metadata:
        raise ValueError("Reflectance asset lacks explicit radiometric scale/offset")
    return raw * float(metadata["scale"]) + float(metadata["offset"])
