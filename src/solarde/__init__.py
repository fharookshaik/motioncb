"""solarde: ablation study on ground-mounted PV segmentation in Germany from open satellite imagery."""

import os

# The locked geospatial wheels bundle their own data. Inherited PostGIS settings can
# select an incompatible proj.db; isolate this Python process, not the user's machine.
for _key in ("PROJ_LIB", "PROJ_DATA", "GDAL_DATA"):
    os.environ.pop(_key, None)

__version__ = "0.1.0"
