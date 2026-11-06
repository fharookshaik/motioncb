# M1.5 polygon-semantics review

**Status 2026-11-06: optional, not required.** Manual review waived in favor of author-documented
mapping semantics; see `docs/decisions.md`. Manske et al. (2022), §3.2
(<https://doi.org/10.3390/data7090128>) defines outer edges of coherent PV modules, not fences.
V20260203 cites that methodology, but release-wide adherence has not been independently audited.
Existing sample and blank CSV remain unreviewed. Instructions below are retained only for an
optional future check; their completion requirements no longer gate M1.5.

Goal: determine whether label outlines follow **panel rows** or the **site/fence boundary**.
Review 100 randomly sampled label-v1 polygons. No QGIS project file is required.

## Files

In `runs/audit_m1_5/`:

- `polygons.gpkg`, layer `polygons`: sampled outlines in EPSG:3035, with original label fields.
- `review_form.csv`: one row per polygon; fill only the final four columns.
- `sample_manifest.json`: seed, source-label SHA-256, sampling population and selected area IDs.
- `README.md`: these instructions.

Sample: uniform without replacement from **all v1 polygons**, including ignore labels and
outside-Germany sites; seed 20261106. This checks source-outline semantics, not model accuracy.
Do not drop difficult cases or replace them with easier sites.

## Load into QGIS

1. Open QGIS. Drag `polygons.gpkg` onto the map and choose layer `polygons`.
2. Right-click the layer → Properties → Symbology. Choose **Simple fill**, set fill to
   **No brush**, and use a bright, thin outline (about 0.4 mm). Labels → Single labels → `audit_id`.
3. Add a high-resolution satellite basemap you are allowed to view. For example, in Browser →
   XYZ Tiles → New Connection, name it `Esri World Imagery` and enter:
   `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`
   Follow provider terms and attribution. An official state orthophoto service is another option.
   Basemap access uses your own QGIS session; the export contains no downloaded imagery.
4. Keep polygon layer above basemap. Open its attribute table, sort `audit_id` ascending,
   select `P001`, then use **Zoom map to selected rows**. Repeat through `P100`.
5. Open `review_form.csv` in a spreadsheet or text editor. Keep `audit_id` and `area_id` intact.
   Save as CSV, not XLSX. Do not edit the GeoPackage geometries or source labels.

## Inspect each polygon

1. Zoom close enough to see row ends and any fence, access road, grass strip or site margin.
   Compare several boundary sides, not only one corner. Toggle the outline layer off/on if it
   obscures details. Also zoom out to understand the full site.
2. Enter exactly one `outline_class` value from the list below.
3. Enter `imagery_source` (provider/service name) and `imagery_date` if shown. Use an ISO date
   such as `2025-06-15`, a year if that is all you know, or `unknown`. Do not use today's access
   date as the imagery acquisition date. Note different dates across a mosaic when apparent.
4. Enter short evidence in `notes`, especially for mixed, unclear or unavailable sites.
   New construction, removed panels, seasonal obstruction or shifted imagery may prevent a
   reliable judgment. Do not infer original label quality from a newer/older scene alone.

### Allowed `outline_class` values

- `panel_rows`: outline closely tracks outer panel-row footprint; most non-panel site margins
  are excluded. It need not trace every gap between rows.
- `fence_site`: outline follows visible fence or clearly identifiable site perimeter, including
  non-panel margins/roads/grass. Do not assume a fence merely because a small buffer exists.
- `mixed`: clear evidence of both conventions within the same polygon. Explain which edges.
- `unclear`: imagery exists, but fence/panel distinction cannot be resolved confidently, or
  misalignment/date mismatch prevents classification. Explain why.
- `not_visible`: no usable high-resolution imagery or no identifiable PV installation. Explain.

Blank means **not yet reviewed**, not “unclear”. Keep all 100 rows, including ignore-labelled cases.
If unsure between panel rows and fence/site, choose `unclear`; no forced guesses.

## Finish

Return the path to the completed `runs/audit_m1_5/review_form.csv` and mention any systematic
imagery problem. Keep original sampled files. No `.qgs`, screenshots or label edits are needed.
M1.5 remains open until the review is checked and a paragraph is appended to `docs/decisions.md`.
That paragraph will give category counts, unassessable cases and the resulting boundary convention;
no conclusion is pre-filled before your inspection.

Regenerate only into a **new** directory if needed:
`uv run python scripts/make_semantics_sample.py --config configs/data.yaml --output runs/audit_m1_5/replacement`
`make audit-semantics` refuses to overwrite an existing audit directory, protecting completed work.

## Attribution and use

Derived polygons: Manske (2026); BNetzA MaStR; UFZ/MaStR release V20260203; **dl-de/by-2-0**
(<https://www.govdata.de/dl-de/by-2-0>). Basemap imagery belongs to its provider and is for inspection
only: never model input, training labels derived from imagery, or redistributed paper figures.
