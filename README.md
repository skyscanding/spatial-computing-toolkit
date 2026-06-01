# Spatial Computing Toolkit

GIS analysis pipelines for urban spatial computing research — developed and validated on the **Tung Chung TOD** case study (Hong Kong).

## What's Inside

| Tool | Description | Runtime | License |
|------|-------------|---------|---------|
| [**QGIS Cookbook**](qgis-cookbook/) | 300+ CLI recipes for spatial analysis — no GUI needed | QGIS 3.x (free) | MIT |
| [**GWR Pipeline**](gwr-pipeline/) | 6-step arcpy pipeline: POI classification → dasymetric population → indicator grid → GWR fit → future prediction → network flow assignment | ArcGIS Pro 3.x | MIT |

## QGIS Cookbook

A comprehensive **QGIS 3.44** command-line reference covering the full spatial analysis workflow. Everything via `qgis_process` and GDAL — no mouse clicks.

**What you can do:**
- Data exploration (`ogrinfo`, `gdalinfo`)
- Coordinate re-projection (EPSG:2326 Hong Kong 1980 Grid)
- Spatial filtering & clipping by boundary, extent, or attribute
- Geometry operations: buffer, dissolve, centroid, voronoi, fix invalid geometries
- Field calculations with `CASE WHEN` for classification
- Spatial joins: count points in polygons, sum line lengths, nearest-neighbor joins
- Network analysis: shortest paths, service areas (isochrones)
- Grid statistics: zonal statistics, raster sampling
- GWR via SAGA
- Cartography: print layout export to PNG/PDF

Includes 4 complete, copy-paste-ready bash script workflows for common spatial data processing chains.

📖 **[Browse the Cookbook →](qgis-cookbook/)**

## GWR Pipeline

An automated arcpy pipeline that uses **Geographically Weighted Regression** to model how facility distribution relates to built-environment indicators — then predicts future distribution under population and infrastructure growth scenarios.

**Validated against**: Tung Chung Tat Tung Road Bus Terminus (4.61 ha TOD site, 100k+ catchment population, TCNTE 2033 projections).

**Pipeline steps:**

```
Step 1: POI Time Classification     → Classify facilities as day/night/all-day
Step 2: Dasymetric Population        → Census blocks → building-level (by height)
Step 3: Indicator Grid               → 50m fishnet + spatial joins
Step 4: GWR Model Fit                → Spatially-varying regression (arcpy.stats.GWR)
Step 5: Future Prediction            → Apply model to TCNTE 2033 scenario
Step 5b: Network Flow Assignment     → Pedestrian LOS + gap detection (networkx)
```

Fully configurable via JSON. Robust field-name resolution — set your column names once, scripts auto-detect or fail with clear messages.

📖 **[Read the full documentation →](gwr-pipeline/)**

## Repository Structure

```
spatial-computing-toolkit/
├── README.md                       ← You are here
├── .gitignore
├── LICENSE
├── qgis-cookbook/
│   └── README.md                   ← 300+ QGIS CLI recipes
└── gwr-pipeline/
    ├── README.md                   ← Full documentation + Tung Chung case study
    ├── requirements.txt
    ├── config_template.json
    └── scripts/
        ├── _utils.py
        ├── master_pipeline.py
        ├── step1_classify_poi.py
        ├── step2_pop_allocate.py
        ├── step3_build_grid.py
        ├── step4_gwr_model.py
        └── step5_net_assign.py
```

## Getting Started

### QGIS Cookbook
```bash
# List all available QGIS processing algorithms
"D:\QGIS\bin\qgis_process-qgis.bat" list

# Run any recipe from the cookbook
"D:\QGIS\bin\qgis_process-qgis.bat" run native:buffer \
  --INPUT="site.shp" --DISTANCE=600 --OUTPUT="site_buf600.gpkg"
```

### GWR Pipeline
```bash
# Install dependencies
pip install -r gwr-pipeline/requirements.txt

# Edit config
cp gwr-pipeline/config_template.json my_project.json

# Run
python gwr-pipeline/scripts/master_pipeline.py my_project.json
```

Requires ArcGIS Pro 3.x with arcpy.

## Case Study: Tung Chung TOD

Both tools were developed for the **Tung Chung Tat Tung Road Bus Terminus** design studio:

- **Site**: 4.61 ha, Sports Centre programme
- **Data**: 1,184 POIs, 598 buildings, 2,408 road segments, 100,531 catchment population
- **Future scenario**: TCNTE 2033 — population 116k → 320k, +877,000 m² GFA
- **Key findings**: 50 pedestrian segments at LOS E (capacity exceeded), 1 critical connectivity gap across highway, evening economy gap identified via POI time classification

## License

MIT
