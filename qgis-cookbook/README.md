# QGIS Spatial Analysis Cookbook

> QGIS 3.44 | Install path `D:\QGIS` | 298 native algorithms + GRASS 8.4 + SAGA + GDAL 3.11

---

## Table of Contents

1. [Environment Setup](#environment-setup)
2. [Data Exploration](#data-exploration)
3. [Coordinate Projection](#coordinate-projection)
4. [Spatial Filtering & Clipping](#spatial-filtering--clipping)
5. [Geometry Operations](#geometry-operations)
6. [Attributes & Fields](#attributes--fields)
7. [Spatial Joins & Aggregation](#spatial-joins--aggregation)
8. [Network Analysis](#network-analysis)
9. [Grid & Zonal Statistics](#grid--zonal-statistics)
10. [Spatial Regression](#spatial-regression)
11. [Data Export](#data-export)
12. [Cartographic Output](#cartographic-output)
13. [Workflow Examples](#workflow-examples)

---

## Environment Setup

```bash
# qgis_process — QGIS processing framework CLI (most commonly used)
D:\QGIS\bin\qgis_process-qgis.bat [command] [algorithm] [parameters]

# QGIS-bundled Python interpreter (for PyQGIS scripts)
D:\QGIS\bin\python-qgis.bat script.py

# GDAL vector tools
D:\QGIS\bin\ogrinfo.exe    # inspect vector data
D:\QGIS\bin\ogr2ogr.exe    # vector conversion & filtering

# GDAL raster tools
D:\QGIS\bin\gdalinfo.exe     # inspect raster data
D:\QGIS\bin\gdalwarp.exe     # raster reprojection & clipping
D:\QGIS\bin\gdal_translate.exe # raster format conversion
```

---

## Data Exploration

### Inspect Shapefile

```bash
# Summary info (CRS, field names & types, geometry type, feature count)
"D:\QGIS\bin\ogrinfo.exe" data.shp -so

# All attributes (with first 5 record values)
"D:\QGIS\bin\ogrinfo.exe" data.shp -al -limit 5
```

### Inspect GeoPackage

```bash
# List layers
"D:\QGIS\bin\ogrinfo.exe" data.gpkg

# Inspect a specific layer
"D:\QGIS\bin\ogrinfo.exe" data.gpkg layer_name -so

# Layer attributes + first 5 records
"D:\QGIS\bin\ogrinfo.exe" data.gpkg layer_name -al -limit 5
```

### Inspect Raster

```bash
"D:\QGIS\bin\gdalinfo.exe" raster.tif
```

### GUI Method

- Drag and drop files into the Layers panel
- Expand GPKG in Browser Panel to see internal layers
- Right-click layer → Properties → Information
- Right-click layer → Open Attribute Table

---

## Coordinate Projection

### Vector Reprojection

```bash
# qgis_process
"D:\QGIS\bin\qgis_process-qgis.bat" run native:reprojectlayer \
  --INPUT="input.shp" \
  --TARGET_CRS="EPSG:2326" \
  --OUTPUT="output_2326.gpkg"

# GDAL (lighter, better for large files)
"D:\QGIS\bin\ogr2ogr.exe" -t_srs EPSG:2326 output.shp input.shp
```

Common Hong Kong coordinate systems:
| EPSG | Name | Unit |
|------|------|------|
| 4326 | WGS84 | degrees |
| 2326 | Hong Kong 1980 Grid | metres |

### Raster Reprojection

```bash
"D:\QGIS\bin\gdalwarp.exe" -t_srs EPSG:2326 output.tif input.tif
```

### Check current CRS

```bash
"D:\QGIS\bin\ogrinfo.exe" data.shp -so | findstr "SRS"
"D:\QGIS\bin\gdalinfo.exe" raster.tif | findstr "SRS"
```

---

## Spatial Filtering & Clipping

### Filter by Location (keeps full geometry)

```bash
# Extract all features that intersect the boundary
"D:\QGIS\bin\qgis_process-qgis.bat" run native:extractbylocation \
  --INPUT="all_features.gpkg" \
  --INTERSECT="boundary.shp" \
  --PREDICATE=intersects \
  --OUTPUT="filtered.gpkg"
```

PREDICATE options: `intersects` | `contains` | `within` | `touches` | `crosses` | `overlaps` | `disjoint`

### Clip (trims geometry to boundary)

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:clip \
  --INPUT="all_features.gpkg" \
  --OVERLAY="boundary.shp" \
  --OUTPUT="clipped.gpkg"
```

### Filter by Rectangular Extent

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:extractbyextent \
  --INPUT="all_features.gpkg" \
  --EXTENT="811000,816000,813000,818000 [EPSG:2326]" \
  --OUTPUT="extent_subset.gpkg"
```

### Filter by Attribute Expression

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:extractbyexpression \
  --INPUT="data.gpkg" \
  --EXPRESSION='"population" > 100 AND "district" = '\''TC'\''' \
  --OUTPUT="filtered.gpkg"
```

### Filter by Geometry Type

```bash
# Keep only line features
"D:\QGIS\bin\qgis_process-qgis.bat" run native:filterbygeometry \
  --INPUT="mixed.gpkg" --LINES=true --POINTS=false --POLYGONS=false \
  --OUTPUT="lines_only.gpkg"
```

### GDAL Method (best for very large files, no memory load)

```bash
# Filter by rectangular extent
"D:\QGIS\bin\ogr2ogr.exe" -spat 811000 816000 813000 818000 output.shp input.shp

# Filter by SQL WHERE clause
"D:\QGIS\bin\ogr2ogr.exe" -where "population > 100" output.shp input.shp

# Clip to polygon boundary
"D:\QGIS\bin\ogr2ogr.exe" -clipsrc boundary.shp output.shp input.shp
```

---

## Geometry Operations

### Buffer

```bash
# Single-distance buffer
"D:\QGIS\bin\qgis_process-qgis.bat" run native:buffer \
  --INPUT="site.shp" --DISTANCE=600 --OUTPUT="site_600m.gpkg"

# Multi-ring buffer (200m, 600m, 1500m simultaneously)
"D:\QGIS\bin\qgis_process-qgis.bat" run native:multiringconstantbuffer \
  --INPUT="site.shp" --RINGS="200,600,1500" --OUTPUT="multi_buf.gpkg"
```

### Dissolve (merge multiple polygons into one)

```bash
# Dissolve all
"D:\QGIS\bin\qgis_process-qgis.bat" run native:dissolve \
  --INPUT="polygons.gpkg" --OUTPUT="merged.gpkg"

# Dissolve grouped by field
"D:\QGIS\bin\qgis_process-qgis.bat" run native:dissolve \
  --INPUT="polygons.gpkg" --FIELD="class" --OUTPUT="by_class.gpkg"
```

### Extract Centroids

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:centroids \
  --INPUT="polygons.gpkg" --OUTPUT="centroids.gpkg"
```

### Add Geometry Attributes (area / length / perimeter)

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:exportaddgeometrycolumns \
  --INPUT="features.gpkg" --CALC_METHODS=0,1 --OUTPUT="with_geom.gpkg"
```
CALC_METHODS: 0=area, 1=perimeter/length, 2=centroid X, 3=centroid Y, 4=point X, 5=point Y

### Explode & Merge

```bash
# Multi-part → single-part (MultiLineString → individual LineStrings)
"D:\QGIS\bin\qgis_process-qgis.bat" run native:multiparttosingleparts \
  --INPUT="multipart.gpkg" --OUTPUT="single.gpkg"

# Single-part → multi-part
"D:\QGIS\bin\qgis_process-qgis.bat" run native:promotetomulti \
  --INPUT="single.gpkg" --OUTPUT="multi.gpkg"

# Merge multiple layers
"D:\QGIS\bin\qgis_process-qgis.bat" run native:mergevectorlayers \
  --LAYERS="layer_a.gpkg;layer_b.shp;layer_c.shp" --OUTPUT="merged.gpkg"
```

### Spatial Overlay

```bash
# Intersection (keep overlapping parts)
"D:\QGIS\bin\qgis_process-qgis.bat" run native:intersection \
  --INPUT="layer_a.gpkg" --OVERLAY="layer_b.gpkg" --OUTPUT="intersection.gpkg"

# Difference (A minus overlapping part with B)
"D:\QGIS\bin\qgis_process-qgis.bat" run native:difference \
  --INPUT="layer_a.gpkg" --OVERLAY="layer_b.gpkg" --OUTPUT="difference.gpkg"

# Union
"D:\QGIS\bin\qgis_process-qgis.bat" run native:union \
  --INPUT="layer_a.gpkg" --OVERLAY="layer_b.gpkg" --OUTPUT="union.gpkg"

# Symmetrical difference (keep non-overlapping parts)
"D:\QGIS\bin\qgis_process-qgis.bat" run native:symmetricaldifference \
  --INPUT="layer_a.gpkg" --OVERLAY="layer_b.gpkg" --OUTPUT="symdiff.gpkg"
```

### Other Common Geometry Operations

```bash
# Convex hull
"D:\QGIS\bin\qgis_process-qgis.bat" run native:convexhull \
  --INPUT="points.gpkg" --OUTPUT="convex_hull.gpkg"

# Voronoi polygons
"D:\QGIS\bin\qgis_process-qgis.bat" run native:voronoipolygons \
  --INPUT="points.gpkg" --BUFFER=200 --OUTPUT="voronoi.gpkg"

# Polygons to lines
"D:\QGIS\bin\qgis_process-qgis.bat" run native:polygonstolines \
  --INPUT="polygons.gpkg" --OUTPUT="boundaries.gpkg"

# Simplify geometry
"D:\QGIS\bin\qgis_process-qgis.bat" run native:simplifygeometries \
  --INPUT="complex.gpkg" --METHOD=0 --TOLERANCE=5 --OUTPUT="simplified.gpkg"

# Fix invalid geometries
"D:\QGIS\bin\qgis_process-qgis.bat" run native:fixgeometries \
  --INPUT="broken.gpkg" --OUTPUT="fixed.gpkg"
```

---

## Attributes & Fields

### Field Calculator

The most powerful attribute manipulation tool in QGIS.

**Basic operations**:
```bash
# Create a numeric field
"D:\QGIS\bin\qgis_process-qgis.bat" run native:fieldcalculator \
  --INPUT="data.gpkg" \
  --FIELD_NAME="ratio" --FIELD_TYPE=0 \
  --FORMULA='"pop" * 1000 / "area"' \
  --OUTPUT="with_ratio.gpkg"

# Create a text field
"D:\QGIS\bin\qgis_process-qgis.bat" run native:fieldcalculator \
  --INPUT="data.gpkg" \
  --FIELD_NAME="label" --FIELD_TYPE=2 --FIELD_LENGTH=50 \
  --FORMULA="'\''Zone '\'' || \"zone_id\" || '\'': '\'' || round(\"pop\", 0)" \
  --OUTPUT="with_label.gpkg"
```

FIELD_TYPE: 0=Float, 1=Integer, 2=String

**Conditional classification (CASE WHEN)**:
```bash
# Numeric classification: classify POIs into 3 types by midType
"D:\QGIS\bin\qgis_process-qgis.bat" run native:fieldcalculator \
  --INPUT="poi.gpkg" \
  --FIELD_NAME="time_class" --FIELD_TYPE=1 \
  --FORMULA="CASE WHEN \"midType\" IN ('公司','银行','学校','培训机构','会展中心','科研机构') THEN 1 WHEN \"midType\" IN ('休闲餐饮场所','茶艺馆','冷饮店','休闲场所') THEN 2 ELSE 3 END" \
  --OUTPUT="poi_classified.gpkg"

# Text classification: Level of Service grading
"D:\QGIS\bin\qgis_process-qgis.bat" run native:fieldcalculator \
  --INPUT="edges.gpkg" \
  --FIELD_NAME="LOS" --FIELD_TYPE=2 --FIELD_LENGTH=1 \
  --FORMULA="CASE WHEN \"flow_pmpm\" >= 0.817 THEN 'E' WHEN \"flow_pmpm\" >= 0.550 THEN 'D' WHEN \"flow_pmpm\" >= 0.383 THEN 'C' ELSE 'B' END" \
  --OUTPUT="edges_los.gpkg"
```

**Common functions**:
```sql
-- Geometry functions
$area               -- area
$length             -- length
$x                  -- centroid X coordinate
$y                  -- centroid Y coordinate
geom_to_wkt($geometry)  -- convert to WKT text

-- Math functions
abs("field")        -- absolute value
round("field", 2)   -- round to N decimals
maximum("field")    -- global maximum of the field
minimum("field")    -- global minimum of the field
mean("field")       -- global mean of the field

-- String functions
"a" || "b"          -- string concatenation
substr("name", 1, 5)  -- extract substring
regexp_match("name", 'pattern')  -- regex match

-- Null handling
coalesce("field", 0)  -- replace null with 0
```

### Other Field Operations

```bash
# Delete a field
"D:\QGIS\bin\qgis_process-qgis.bat" run native:deletecolumn \
  --INPUT="data.gpkg" --COLUMN="unused" --OUTPUT="cleaned.gpkg"

# Rename a field
"D:\QGIS\bin\qgis_process-qgis.bat" run native:renametablefield \
  --INPUT="data.gpkg" --FIELD="old_name" --NEW_NAME="new_name" --OUTPUT="renamed.gpkg"

# Keep only specified fields
"D:\QGIS\bin\qgis_process-qgis.bat" run native:retainfields \
  --INPUT="data.gpkg" --FIELDS="id;name;value" --OUTPUT="subset.gpkg"

# Add auto-increment ID field
"D:\QGIS\bin\qgis_process-qgis.bat" run native:addautoincrementalfield \
  --INPUT="data.gpkg" --FIELD_NAME="uid" --OUTPUT="with_id.gpkg"

# Add X/Y coordinate fields
"D:\QGIS\bin\qgis_process-qgis.bat" run native:addxyfields \
  --INPUT="points.gpkg" --OUTPUT="with_xy.gpkg"

# Sort by expression
"D:\QGIS\bin\qgis_process-qgis.bat" run native:orderbyexpression \
  --INPUT="data.gpkg" --EXPRESSION='"flow"' --ASCENDING=false --OUTPUT="sorted.gpkg"
```

---

## Spatial Joins & Aggregation

### Join by Field Value (like Excel VLOOKUP)

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:joinattributestable \
  --INPUT="main.gpkg" --FIELD="id" \
  --INPUT_2="lookup.gpkg" --FIELD_2="id" \
  --JOIN_FIELDS="name;category" \
  --OUTPUT="joined.gpkg"
```

### Join by Location + Summarize

```bash
# Count points in each polygon, plus attribute summaries
"D:\QGIS\bin\qgis_process-qgis.bat" run native:joinbylocationsummary \
  --INPUT="polygons.gpkg" \
  --JOIN="points.gpkg" \
  --PREDICATE=intersects \
  --SUMMARIES=1,5 `# 1=count, 5=sum` \
  --JOIN_FIELDS="population" \
  --OUTPUT="spatial_join.gpkg"
```

SUMMARIES options: 1=count, 2=unique, 3=min, 4=max, 5=sum, 6=mean, 7=median, 8=stddev, 9=minority, 10=majority, 11=range, 12=q1, 13=q3, 14=iqr

### Join by Nearest

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:joinbynearest \
  --INPUT="points.gpkg" \
  --INPUT_2="hubs.gpkg" \
  --NEIGHBORS=1 \
  --OUTPUT="nearest.gpkg"
```

### Aggregate (Group By)

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:aggregate \
  --INPUT="data.gpkg" \
  --GROUP_FIELDS="district" \
  --AGGREGATES="1,5,6:population,6:area" \
  --OUTPUT="aggregated.gpkg"
```

AGGREGATES format: `aggregate_type:field_name`, multiple separated by commas. Aggregate types are the same as SUMMARIES above.

### Count Points in Polygons

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:countpointsinpolygon \
  --POLYGONS="grid.gpkg" \
  --POINTS="poi.gpkg" \
  --CLASSWEIGHT="category" --FIELD="poi_count" \
  --OUTPUT="grid_with_counts.gpkg"
```

### Sum Line Lengths in Polygons

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:sumlinelengths \
  --INPUT="grid.gpkg" \
  --LINES="roads.gpkg" \
  --LEN_FIELD="road_length" --COUNT_FIELD="road_segments" \
  --OUTPUT="grid_road_density.gpkg"
```

---

## Network Analysis

### Network Preprocessing

Ensure segment endpoints are properly connected before analysis:

```bash
# 1. Fix geometries
"D:\QGIS\bin\qgis_process-qgis.bat" run native:fixgeometries \
  --INPUT="roads.gpkg" --OUTPUT="roads_fixed.gpkg"

# 2. Explode polylines → individual segments
"D:\QGIS\bin\qgis_process-qgis.bat" run native:explodelines \
  --INPUT="roads_fixed.gpkg" --OUTPUT="roads_exploded.gpkg"

# 3. Snap endpoints (connect endpoints within 2m)
"D:\QGIS\bin\qgis_process-qgis.bat" run native:snapgeometries \
  --INPUT="roads_exploded.gpkg" \
  --REFERENCE_LAYER="roads_exploded.gpkg" \
  --TOLERANCE=2 --BEHAVIOR=3 \
  --OUTPUT="roads_snapped.gpkg"
```

### Point-to-Point Shortest Path

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:shortestpathpointtopoint \
  --INPUT="roads_snapped.gpkg" \
  --STRATEGY=0 \
  --START_POINT="811700,816900 [EPSG:2326]" \
  --END_POINT="812500,817500 [EPSG:2326]" \
  --OUTPUT="shortest_path.gpkg"
```
STRATEGY: 0=shortest distance, 1=fastest path

### Layer-to-Point Shortest Path (batch origins → single destination)

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:shortestpathlayertopoint \
  --INPUT="roads_snapped.gpkg" \
  --STRATEGY=0 \
  --START_POINTS="origins.gpkg" \
  --END_POINT="812500,817500 [EPSG:2326]" \
  --OUTPUT="paths.gpkg"
```

### Service Area (Isochrone / Walkshed)

```bash
# From a single point: 5/10/15 minute walking range
"D:\QGIS\bin\qgis_process-qgis.bat" run native:serviceareafrompoint \
  --INPUT="roads_snapped.gpkg" \
  --STRATEGY=1 \
  --START_POINT="811700,816900 [EPSG:2326]" \
  --TRAVEL_COST="300,600,900" \
  --OUTPUT="service_area.gpkg"
```
TRAVEL_COST units depend on edge weight field: if edge weight is length (metres), use metres; if time (seconds), use seconds.

### Service Area from Layer

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:serviceareafromlayer \
  --INPUT="roads_snapped.gpkg" \
  --STRATEGY=1 \
  --START_POINTS="facilities.gpkg" \
  --TRAVEL_COST="300,600,900" \
  --OUTPUT="multi_service_area.gpkg"
```

### Flow Assignment (Network Flow Accumulation)

QGIS native tools can only compute **single shortest paths** — they cannot **accumulate flows from multiple OD pairs onto the same road segment**.

For multi-origin flow accumulation (e.g. 100 residential blocks → 1 destination, with all shortest paths overlaid), use PyQGIS with networkx. Basic approach:

```
qgis_process preprocessing (buffer / clip / network preparation)
    ↓
networkx reads roads → builds graph
    ↓
Batch shortest path + flow accumulation on segments
    ↓
qgis_process postprocessing (LOS classification / export)
```

See full script in [Workflow Example — Network Flow Assignment](#example-3-network-flow-assignment-pyqgis-script).

---

## Grid & Zonal Statistics

### Create Grid

```bash
# Rectangular grid 50m × 50m
"D:\QGIS\bin\qgis_process-qgis.bat" run native:creategrid \
  --TYPE=2 --EXTENT="810800,816000,813800,819000 [EPSG:2326]" \
  --HSPACING=50 --VSPACING=50 \
  --OUTPUT="grid_50m.gpkg"

# Hexagonal grid 100m
"D:\QGIS\bin\qgis_process-qgis.bat" run native:creategrid \
  --TYPE=4 --EXTENT="810800,816000,813800,819000 [EPSG:2326]" \
  --HSPACING=100 \
  --OUTPUT="hex_grid.gpkg"
```
TYPE: 0=points, 1=lines, 2=rectangles, 3=diamonds, 4=hexagons

### Zonal Statistics (extract raster values to vector polygons)

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:zonalstatisticsfb \
  --INPUT="zones.gpkg" \
  --RASTER="population.tif" \
  --COLUMN_PREFIX="pop_" \
  --STATISTICS="1,2,4,5,6" \
  --OUTPUT="zones_with_stats.gpkg"
```
STATISTICS: 1=Count, 2=Sum, 3=Minority, 4=Mean, 5=Stddev, 6=Min, 7=Max, 8=Range, 9=Median, 10=Majority

### Raster Sampling (extract point values from raster)

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:rastersampling \
  --INPUT="points.gpkg" \
  --RASTERCOPY="elevation.tif" \
  --COLUMN_PREFIX="dem_" \
  --OUTPUT="points_with_elev.gpkg"
```

### Raster Pixels to Vector

```bash
# To points
"D:\QGIS\bin\qgis_process-qgis.bat" run native:pixelstopoints \
  --INPUT="raster.tif" --OUTPUT="raster_points.gpkg"

# To polygons
"D:\QGIS\bin\qgis_process-qgis.bat" run native:pixelstopolygons \
  --INPUT="raster.tif" --OUTPUT="raster_polygons.gpkg"
```

---

## Spatial Regression

### GWR — Geographically Weighted Regression (SAGA)

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run saga:geographicallyweightedregression \
  --POINTS="grid_data.gpkg" \
  --DEPENDENT="poi_count" \
  --PREDICTORS="pop_density;road_density;lucc_commercial" \
  --SEARCH_RANGE=ADAPTIVE \
  --BW="500" \
  --KERNEL="gaussian" \
  --COEFFICIENTS="gwr_coefficients.gpkg" \
  --RESIDUALS="gwr_residuals.gpkg"
```

### Other Statistical Methods

```bash
# Basic statistics (count/mean/std/min/max of fields)
"D:\QGIS\bin\qgis_process-qgis.bat" run native:basicstatisticsforfields \
  --INPUT="data.gpkg" --FIELD_NAMES="pop;area;ratio" --OUTPUT="stats.html"

# Nearest Neighbour Analysis (assess point clustering)
"D:\QGIS\bin\qgis_process-qgis.bat" run native:nearestneighbouranalysis \
  --INPUT="points.gpkg" --OUTPUT="nn_analysis.html"

# K-means clustering
"D:\QGIS\bin\qgis_process-qgis.bat" run native:kmeansclustering \
  --INPUT="data.gpkg" --CLUSTERS=5 --FIELDS="x;y;value" --OUTPUT="clusters.gpkg"

# DBSCAN clustering (density-based)
"D:\QGIS\bin\qgis_process-qgis.bat" run native:dbscanclustering \
  --INPUT="points.gpkg" --MIN_SIZE=5 --EPS=100 --OUTPUT="dbscan.gpkg"
```

---

## Data Export

### Save Vector Layers

```bash
# Save as GPKG
"D:\QGIS\bin\qgis_process-qgis.bat" run native:savefeatures \
  --INPUT="processed.gpkg" \
  --LAYER_NAME="my_layer" \
  --OUTPUT="final.gpkg"

# Save as Shapefile
"D:\QGIS\bin\qgis_process-qgis.bat" run native:savefeatures \
  --INPUT="processed.gpkg" --OUTPUT="final.shp"

# Export selected features
"D:\QGIS\bin\qgis_process-qgis.bat" run native:saveselectedfeatures \
  --INPUT="data.gpkg" --OUTPUT="selected_only.gpkg"
```

### Export to Spreadsheet

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:exporttospreadsheet \
  --INPUT="data.gpkg" --OUTPUT="output.xlsx"
```

### ogr2ogr — Create Multi-Layer GPKG

```bash
# First layer
"D:\QGIS\bin\ogr2ogr.exe" -f GPKG output.gpkg layer_a.shp -nln layer_a

# Append second layer
"D:\QGIS\bin\ogr2ogr.exe" -f GPKG -update output.gpkg layer_b.shp -nln layer_b

# Append third layer (with CRS conversion)
"D:\QGIS\bin\ogr2ogr.exe" -f GPKG -update -t_srs EPSG:2326 output.gpkg layer_c.shp -nln layer_c
```

### Export to DXF (CAD format)

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:dxfexport \
  --LAYERS="roads.gpkg;buildings.shp" \
  --SYMBOLOGY_MODE=0 --SYMBOLOGY_SCALE=1000 \
  --OUTPUT="export.dxf"
```

---

## Cartographic Output

### Print Layout Export (requires pre-configured layout in QGIS project)

```bash
# Export as image
"D:\QGIS\bin\qgis_process-qgis.bat" run native:printlayouttoimage \
  --LAYOUT="my_layout" --DPI=300 --OUTPUT="map.png"

# Export as PDF
"D:\QGIS\bin\qgis_process-qgis.bat" run native:printlayouttopdf \
  --LAYOUT="my_layout" --DPI=300 --OUTPUT="map.pdf"

# If layout is in a specific project file, add PROJECT_PATH
"D:\QGIS\bin\qgis_process-qgis.bat" run native:printlayouttoimage \
  --PROJECT_PATH="project.qgz" --LAYOUT="my_layout" --DPI=250 \
  --OUTPUT="output.png"
```

### Atlas Batch Export

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:atlaslayouttopdf \
  --LAYOUT="atlas" --COVERAGE_LAYER="grid.gpkg" --DPI=200 \
  --OUTPUT="atlas_output.pdf"
```

### GUI Method (recommended for cartography)

`Project → New Print Layout` lets you interactively design maps in the GIS window:
- **Add Map** — insert a map view, choose displayed layers
- **Add Legend** — auto-generate legend
- **Add Scale Bar** — add a scale bar
- **Add Label** — title and annotations
- **Layer Styling Panel** — configure per-layer styles:
  - Single Symbol — uniform style
  - Categorized — colour by field value (e.g. land-use type)
  - Graduated — gradient by numeric value (e.g. population density, flow)
  - Rule-based — complex conditional styling

---

## Workflow Examples

### Example 1: Spatial Data Preprocessing Pipeline

Full chain: load site → buffer → clip roads → filter population → field calculation

```bash
#!/bin/bash
SITE="D:/data/Designsite.shp"
ROADS="D:/data/roads.gpkg"
POP="D:/data/population.gpkg"
OUT="D:/output"
mkdir -p "$OUT"

# Step 1: 600m buffer
"D:\QGIS\bin\qgis_process-qgis.bat" run native:buffer \
  --INPUT="$SITE" --DISTANCE=600 --OUTPUT="$OUT/site_buf600.gpkg"

# Step 2: Clip roads
"D:\QGIS\bin\qgis_process-qgis.bat" run native:clip \
  --INPUT="$ROADS" --OVERLAY="$OUT/site_buf600.gpkg" --OUTPUT="$OUT/roads_clip.gpkg"

# Step 3: Filter population within buffer
"D:\QGIS\bin\qgis_process-qgis.bat" run native:extractbylocation \
  --INPUT="$POP" --INTERSECT="$OUT/site_buf600.gpkg" --PREDICATE=intersects \
  --OUTPUT="$OUT/pop_600m.gpkg"

# Step 4: Add road length field
"D:\QGIS\bin\qgis_process-qgis.bat" run native:exportaddgeometrycolumns \
  --INPUT="$OUT/roads_clip.gpkg" --CALC_METHODS=0 --OUTPUT="$OUT/roads_len.gpkg"

# Step 5: Compute population trips (0.5 trips per person)
"D:\QGIS\bin\qgis_process-qgis.bat" run native:fieldcalculator \
  --INPUT="$OUT/pop_600m.gpkg" --FIELD_NAME="trips" --FIELD_TYPE=0 \
  --FORMULA='"Averag_pop" * 0.5' --OUTPUT="$OUT/pop_trips.gpkg"

echo "Done. Output: $OUT"
```

### Example 2: POI Classification + Grid Statistics

Full chain: POI time classification → create grid → count POIs per category

```bash
#!/bin/bash
POI="D:/data/all_poi.gpkg"
EXTENT="810800,816000,813800,819000 [EPSG:2326]"
OUT="D:/output"
mkdir -p "$OUT"

# Step 1: POI time-of-day classification (field calculator CASE WHEN)
"D:\QGIS\bin\qgis_process-qgis.bat" run native:fieldcalculator \
  --INPUT="$POI" --FIELD_NAME="time_class" --FIELD_TYPE=1 \
  --FORMULA="CASE WHEN \"midType\" IN ('公司','银行','学校','培训机构','科研机构','会展中心') THEN 1 WHEN \"midType\" IN ('休闲餐饮场所','茶艺馆','冷饮店','休闲场所') THEN 2 ELSE 3 END" \
  --OUTPUT="$OUT/poi_classified.gpkg"

# Step 2: Create 50m grid
"D:\QGIS\bin\qgis_process-qgis.bat" run native:creategrid \
  --TYPE=2 --EXTENT="$EXTENT" --HSPACING=50 --VSPACING=50 --OUTPUT="$OUT/grid.gpkg"

# Step 3: Count POIs per category
for TCLASS in 1 2 3; do
  "D:\QGIS\bin\qgis_process-qgis.bat" run native:extractbyexpression \
    --INPUT="$OUT/poi_classified.gpkg" \
    --EXPRESSION="\"time_class\" = $TCLASS" \
    --OUTPUT="$OUT/poi_t${TCLASS}.gpkg"

  "D:\QGIS\bin\qgis_process-qgis.bat" run native:countpointsinpolygon \
    --POLYGONS="$OUT/grid.gpkg" \
    --POINTS="$OUT/poi_t${TCLASS}.gpkg" \
    --FIELD="count_t${TCLASS}" \
    --OUTPUT="$OUT/grid_t${TCLASS}.gpkg"
done

echo "Done. Output: $OUT/grid_t*.gpkg"
```

### Example 3: Network Flow Assignment (PyQGIS Script)

The script below uses `qgis_process` for data pre/post-processing and `networkx` for core shortest-path flow assignment.
Save as `flow_assignment.py`, run with `D:\QGIS\bin\python-qgis.bat flow_assignment.py`.

```python
"""
Network Flow Assignment — Multi-origin → Single destination shortest-path flow accumulation
Run with: D:\QGIS\bin\python-qgis.bat flow_assignment.py
"""
import os, sys
import processing
import networkx as nx
import numpy as np
from shapely.geometry import Point, LineString
from shapely.ops import nearest_points
from qgis.core import QgsVectorLayer, QgsFeature, QgsGeometry, QgsField, QgsFields
from qgis.PyQt.QtCore import QVariant

# ═══════════ Configuration ═══════════
SITE_PATH  = r"D:/data/Designsite.shp"
ROADS_PATH = r"D:/data/roads.gpkg"
POP_PATH   = r"D:/data/population.gpkg"
OUT_DIR    = r"D:/output"
BUFFER_M   = 600
WALK_SPEED = 1.25   # m/s
MAX_WALK_M = 2000   # max walking distance
TRIP_RATE  = 0.5    # trips per person

os.makedirs(OUT_DIR, exist_ok=True)

# ═══════════ Phase 1: qgis_process preprocessing ═══════════
print("[1/4] Preprocessing...")

site_buf = processing.run("native:buffer", {
    'INPUT': SITE_PATH, 'DISTANCE': BUFFER_M,
    'OUTPUT': f'{OUT_DIR}/buf.gpkg'
})['OUTPUT']

roads_clip = processing.run("native:clip", {
    'INPUT': ROADS_PATH, 'OVERLAY': site_buf,
    'OUTPUT': f'{OUT_DIR}/roads_clip.gpkg'
})['OUTPUT']

roads_exp = processing.run("native:explodelines", {
    'INPUT': roads_clip, 'OUTPUT': f'{OUT_DIR}/roads_exploded.gpkg'
})['OUTPUT']

pop_near = processing.run("native:extractbylocation", {
    'INPUT': POP_PATH, 'INTERSECT': site_buf,
    'PREDICATE': [0], 'OUTPUT': f'{OUT_DIR}/pop_near.gpkg'
})['OUTPUT']

# ═══════════ Phase 2: networkx graph construction ═══════════
print("[2/4] Building network graph...")

roads_layer = QgsVectorLayer(roads_exp, "roads", "ogr")
site_layer  = QgsVectorLayer(SITE_PATH, "site", "ogr")

G = nx.Graph()
node_coords = {}
coord_to_node = {}
next_node_id = 0
SNAP = 2.0  # node snap tolerance

def get_or_create_node(x, y):
    global next_node_id
    rx, ry = round(x / SNAP) * SNAP, round(y / SNAP) * SNAP
    key = (rx, ry)
    if key not in coord_to_node:
        nid = next_node_id
        coord_to_node[key] = nid
        node_coords[nid] = (x, y)
        G.add_node(nid, x=x, y=y)
        next_node_id += 1
    return coord_to_node[key]

edge_road_map = {}  # (u, v) → [road_ids]
seg_id = 0

for feat in roads_layer.getFeatures():
    geom = feat.geometry()
    if geom.isMultipart():
        geom = geom.mergeLines()
    pts = geom.asPolyline()
    if len(pts) < 2:
        continue
    u = get_or_create_node(pts[0].x(), pts[0].y())
    v = get_or_create_node(pts[-1].x(), pts[-1].y())
    if u == v:
        continue
    length = geom.length()
    tt = length / WALK_SPEED
    G.add_edge(u, v, weight=tt, length=length, seg_id=seg_id)
    edge_road_map.setdefault((min(u, v), max(u, v)), []).append(seg_id)
    seg_id += 1

print(f"  Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")

# ═══════════ Phase 3: Shortest path + flow accumulation ═══════════
print("[3/4] Flow assignment...")

# Site centroid → nearest node
site_centroid = site_layer.getFeature(1).geometry().centroid()
site_xy = (site_centroid.asPoint().x(), site_centroid.asPoint().y())

graph_nodes = list(G.nodes())
graph_xy = np.array([node_coords[n] for n in graph_nodes])
from scipy.spatial import cKDTree
tree = cKDTree(graph_xy)
_, idx = tree.query(site_xy)
dest_node = graph_nodes[idx]

# Dijkstra — all nodes to destination
sp_dist = nx.single_source_dijkstra_path_length(G, dest_node, weight='weight')
print(f"  Reachable nodes: {len(sp_dist)} / {G.number_of_nodes()}")

# Flow accumulation
seg_flow = np.zeros(seg_id)

pop_layer = QgsVectorLayer(pop_near, "pop", "ogr")
assigned = skipped = 0
total_trips = 0

for feat in pop_layer.getFeatures():
    pop_val = feat['Averag_pop'] or 0
    if pop_val <= 0:
        continue

    pt = feat.geometry().centroid().asPoint()
    _, nidx = tree.query((pt.x(), pt.y()))
    origin_node = graph_nodes[nidx]

    if origin_node not in sp_dist:
        skipped += 1
        continue

    net_dist = sp_dist[origin_node]
    if net_dist > MAX_WALK_M:
        skipped += 1
        continue

    trips = pop_val * TRIP_RATE
    total_trips += trips
    assigned += 1

    try:
        path = nx.shortest_path(G, origin_node, dest_node, weight='weight')
    except nx.NetworkXNoPath:
        skipped += 1
        continue

    for i in range(len(path) - 1):
        u, v = path[i], path[i+1]
        ek = (min(u, v), max(u, v))
        for sid in edge_road_map.get(ek, []):
            seg_flow[sid] += trips

print(f"  Assigned: {assigned} origins, Skipped: {skipped}, Total flow: {total_trips:.0f}")

# ═══════════ Phase 4: Write back + LOS classification ═══════════
print("[4/4] Exporting results...")

# Write flow values to roads layer (via virtual field or layer copy)
# ... (detailed QgsVectorFileWriter code omitted; use qgis_process downstream)

# LOS classification
processing.run("native:fieldcalculator", {
    'INPUT': f'{OUT_DIR}/roads_with_flow.gpkg',
    'FIELD_NAME': 'LOS', 'FIELD_TYPE': 2, 'FIELD_LENGTH': 3,
    'FORMULA': "CASE WHEN \"flow_pmpm\" >= 0.817 THEN 'E' WHEN \"flow_pmpm\" >= 0.550 THEN 'D' WHEN \"flow_pmpm\" >= 0.383 THEN 'C' ELSE 'B' END",
    'OUTPUT': f'{OUT_DIR}/final.gpkg'
})

print(f"Done → {OUT_DIR}/final.gpkg")
```

### Example 4: GWR Prediction Pipeline

Full chain: create grid → spatial statistics → GWR regression → prediction

```bash
#!/bin/bash
EXTENT="810800,816000,813800,819000 [EPSG:2326]"
OUT="D:/output"
mkdir -p "$OUT"

# Step 1: Create 50m grid
"D:\QGIS\bin\qgis_process-qgis.bat" run native:creategrid \
  --TYPE=2 --EXTENT="$EXTENT" --HSPACING=50 --VSPACING=50 \
  --OUTPUT="$OUT/grid.gpkg"

# Step 2: Count POIs per grid cell
"D:\QGIS\bin\qgis_process-qgis.bat" run native:countpointsinpolygon \
  --POLYGONS="$OUT/grid.gpkg" --POINTS="poi.gpkg" \
  --FIELD="poi_count" --OUTPUT="$OUT/grid_poi.gpkg"

# Step 3: Compute road density per grid cell
"D:\QGIS\bin\qgis_process-qgis.bat" run native:sumlinelengths \
  --INPUT="$OUT/grid_poi.gpkg" --LINES="roads.gpkg" \
  --LEN_FIELD="road_len" --COUNT_FIELD="road_n" \
  --OUTPUT="$OUT/grid_poi_road.gpkg"

# Step 4: Zonal statistics — extract values from population raster
"D:\QGIS\bin\qgis_process-qgis.bat" run native:zonalstatisticsfb \
  --INPUT="$OUT/grid_poi_road.gpkg" --RASTER="pop.tif" \
  --COLUMN_PREFIX="pop_" --STATISTICS=2,4,6 \
  --OUTPUT="$OUT/grid_full.gpkg"

# Step 5: GWR (SAGA)
"D:\QGIS\bin\qgis_process-qgis.bat" run saga:geographicallyweightedregression \
  --POINTS="$OUT/grid_full.gpkg" \
  --DEPENDENT="poi_count" \
  --PREDICTORS="pop_sum;road_len" \
  --BW="500" --KERNEL="gaussian" \
  --COEFFICIENTS="$OUT/gwr_coef.gpkg" \
  --RESIDUALS="$OUT/gwr_resid.gpkg"

echo "Done. GWR results: $OUT/gwr_*.gpkg"
```

---

## FAQ

### Why GPKG over SHP?

- GPKG is a single file — SHP requires .shp + .shx + .dbf + .prj (4 files minimum)
- Multiple layers can live in one file
- No 10-character field name limit (SHP enforces this)
- Supports more data types (date, boolean, BLOB)
- Recommendation: use GPKG for intermediate processing; deliver as SHP only if required

### Can I use Chinese paths / Chinese field names?

- Both GPKG and Shapefile support Chinese field names and paths
- However, GDAL CLI tools can be sensitive to quoting with Chinese paths. Prefer English paths, or store Chinese paths in variables

### qgis_process pipelining

Each `qgis_process run` command is an independent process. To chain steps, save intermediate outputs to files:

```bash
# Don't do this (not supported):
qgis_process run buffer | qgis_process run clip   # won't work!

# Do this instead:
qgis_process run buffer --OUTPUT="temp.gpkg"
qgis_process run clip --INPUT="temp.gpkg" --OUTPUT="final.gpkg"
```

You can use Model Builder (`Processing → Graphical Modeler`) to save pipelines as `.model3` files, then execute them with a single command: `qgis_process run model:your_model`.

### How to discover available algorithms?

```bash
# List all algorithms
"D:\QGIS\bin\qgis_process-qgis.bat" list

# Show only native algorithms
"D:\QGIS\bin\qgis_process-qgis.bat" list | findstr "native:"

# Show parameter help for a specific algorithm
"D:\QGIS\bin\qgis_process-qgis.bat" help native:buffer
```

---

## Related Tools

- [GWR Pipeline](../gwr-pipeline/) — ArcGIS Pro arcpy pipeline for facility distribution GWR modelling
- [Spatial Computing Toolkit](../) — project overview

## License

MIT
