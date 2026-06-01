# GWR Pipeline — Geographically Weighted Regression for Facility Distribution

ArcGIS Pro / arcpy pipeline that uses **Geographically Weighted Regression** to model how facility distribution (POIs, services) relates to built-environment indicators — then predicts future distribution from population and infrastructure projections.

No GUI. Entirely command-line driven.

## Core Methodology

```
Population Change (independent variable)
       +
Infrastructure / Transit (co-variates)
       ↓
  GWR Spatial Regression
       ↓
Future Facility Distribution (predicted)
```

**Key insight**: population growth drives facility demand, but the relationship varies spatially. GWR captures this heterogeneity by fitting separate regression models at every location, weighted by nearby observations.

## 5-Step Pipeline

| Step | Name | Input | Output | Tool |
|------|------|-------|--------|------|
| 1 | **POI Classification** | Raw POI by category | Time-classified POI (day/night/all-day) | `CalculateField` |
| 2 | **Dasymetric Population** | Census blocks + buildings | Population per building (elevation-weighted) | `Intersect` |
| 3 | **Indicator Grid** | Site, POI, population, roads | 50m grid with poi_count, pop_density, road_density | `CreateFishnet` + `SpatialJoin` |
| 4 | **GWR Fit** | Active grid cells | GWR model (coefficients, residuals, R²) | `arcpy.stats.GWR` |
| 5 | **Future Prediction** | GWR model + future scenario grid | Predicted facility counts | `arcpy.stats.GWR` (prediction mode) |
| 5b | *(Supplementary)* **Network Assignment** | Road network + population origins | Link loads, LOS, gap zones | `networkx` + arcpy |

## Quick Start

### Prerequisites

- **ArcGIS Pro 3.x** installed (provides `arcpy`)
- Python libraries: `numpy`, `scipy`, `networkx`, `shapely`

```bash
# Install dependencies into your arcgispro-py3 environment
pip install -r requirements.txt
```

### 1. Create a config file

Copy `config_template.json` and fill in your data paths and field names:

```json
{
  "output_gdb": "D:/MyProject/output.gdb",
  "crs": "EPSG:2326",
  "steps": ["grid", "gwr_fit", "gwr_predict"],

  "field_mapping": {
    "population_count": "Averag_pop",
    "building_elevation": "Elevation",
    "road_length": "Shape_Leng"
  },

  "grid": {
    "site_fc": "D:/data/my_site.shp",
    "poi_fc": "D:/data/my_poi.gpkg",
    "pop_fc": "D:/data/my_population.gpkg",
    "roads_fc": "D:/data/my_roads.gpkg",
    "cell_size": 50,
    "study_buffer": 1500
  },

  "gwr": {
    "dependent": "poi_count",
    "explanatory": ["pop_density", "road_density"]
  },

  "prediction": {
    "prediction_fc": "D:/data/future_grid.gpkg",
    "explanatory": ["pop_density", "road_density"]
  }
}
```

> **Field Mapping**: Use the `field_mapping` section to declare your dataset's actual field names. Scripts will use these exact names first, then fall back to auto-detection, then fail with a clear error message listing available fields.

### 2. Run

```bash
# Full pipeline
python scripts/master_pipeline.py my_config.json

# Specific steps only
python scripts/master_pipeline.py my_config.json --steps 3,4,5

# Single step (standalone)
python scripts/step4_gwr_model.py --config my_config.json
```

### 3. View results

All outputs land in the File Geodatabase. Open in ArcGIS Pro or QGIS:

| Layer | Contents |
|-------|----------|
| `grid_indicators_full` | All grid cells with poi_count, pop_density, road_density |
| `grid_active_cells` | Subset with POI > 0 (training data) |
| `gwr_results` | Local R², coefficients, residuals, StdResidual |
| `gwr_prediction_future` | Predicted facility counts for future scenario |
| `poi_all_time_classified` | Merged classified POIs (if step 1 ran) |
| `site_buildings` | Buildings with `bldg_pop` field (if step 2 ran) |
| `link_loads_200m` | Loaded pedestrian edges with LOS (if step 5b ran) |
| `gap_zones` | Connectivity gaps (if step 5b ran) |

## Detailed Steps

### Step 1: POI Time Classification

Classifies facilities into daytime / nighttime / all-day operation based on their `midType` field.

**Why**: Daytime-oriented facilities (offices, banks) cluster around CBDs; nighttime facilities (F&B, leisure) are underrepresented near transit hubs — revealing the *evening economy gap*.

**Script**: `scripts/step1_classify_poi.py`

### Step 2: Dasymetric Population Allocation

Distributes census population from areal units to individual building footprints, weighted by building height (a proxy for GFA: gross floor area).

```
pop_building = census_pop × (footprint_area × height) / Σ(area × height)_per_block
```

**Why**: Census data is areal; buildings are actual dwelling units. Elevation-weighting avoids over-allocating to low-rise structures.

**Script**: `scripts/step2_pop_allocate.py`

### Step 3: Indicator Grid Construction

Creates a regular fishnet grid (default 50m) and spatial-joins three indicators:
1. **poi_count** — facilities intersecting each cell
2. **pop_density** — population per hectare
3. **road_density** — total road length per m² of cell

**Script**: `scripts/step3_build_grid.py`

### Step 4: GWR Model Fitting

Fits a Geographically Weighted Regression model:

```
poi_count_i = β₀(ui,vi) + β₁(ui,vi)·pop_density_i + β₂(ui,vi)·road_density_i + ε_i
```

**Why GWR over OLS**: Facility demand relationships vary spatially. Near metro stations, population density may strongly predict POI count; in rural areas, road access may matter more.

**Script**: `scripts/step4_gwr_model.py`

**Diagnostics to watch**:
- **Local R²** — model fit at each location
- **StdResidual** — values > |2.5| indicate outliers
- **AICc** — lower is better; use for model comparison
- **Condition Number** — > 30 indicates local multicollinearity

### Step 5: Future Scenario Prediction

Applies the fitted GWR model to a future scenario grid (e.g., TCNTE 2033 projections).

**Script**: `scripts/step4_gwr_model.py` (prediction mode)

### Step 5b: Pedestrian Network Flow Assignment

Supplementary analysis: models pedestrian movement through the network to reach the site. Complementary to grid-level GWR — provides the human-scale lens.

**Script**: `scripts/step5_net_assign.py`

**LOS thresholds** (HCM pedestrian, 3m walkway):
- **B**: < 0.38 ped/m/min — free flow
- **C**: 0.38–0.55 — slightly restricted
- **D**: 0.55–0.82 — noticeable restriction
- **E**: ≥ 0.82 — at capacity

## Built-in Classification Dictionaries

### Default Daytime (offices, education, administration)
`公司` `知名企业` `公司企业` `银行` `金融保险服务机构` `银行相关` `中介机构` `邮局` `物流速递` `家居建材市场` `花鸟鱼虫市场` `维修站点` `摄影冲印店` `学校` `培训机构` `科研机构` `传媒机构` `文艺团体` `会展中心` `住宅区`

### Default Nighttime (evening F&B, leisure)
`休闲餐饮场所` `茶艺馆` `冷饮店` `休闲场所`

### Default All-Day (retail, healthcare, sports)
`中餐厅` `外国餐厅` `快餐厅` `咖啡厅` `糕饼店` `甜品店` `餐饮相关场所` `便民商店/便利店` `超级市场` `商场` `专卖店` `服装鞋帽皮具店` `体育用品店` `家电电子卖场` `个人用品/化妆品店` `文化用品店` `购物相关场所` `宾馆酒店` `旅馆招待所` `美容美发店` `洗衣店` `自动提款机` `电讯营业厅` `旅行社` `生活服务场所` `诊所` `综合医院` `专科医院` `急救中心` `医药保健销售店` `医疗保健服务场所` `图书馆` `博物馆` `美术馆` `展览馆` `科教文化场所` `科技馆` `天文馆` `文化宫` `运动场馆` `体育休闲服务场所` `高尔夫相关`

## Full Config Reference

```yaml
# ── Global ──
crs: "EPSG:2326"
steps: [grid, gwr_fit, gwr_predict]

# ── Field Mapping (tells scripts your actual column names) ──
field_mapping:
  population_count: "Averag_pop"
  building_elevation: "Elevation"
  poi_midtype: "midType"
  road_length: "Shape_Leng"
  road_travel_time: null        # set if your roads have a travel_time column
  census_block_id: "ssbg"
  census_block_name: "ssbg_eng"

# ── Grid ──
grid:
  site_fc: <path>
  poi_fc: <path>                # or null to use step 1 result
  pop_fc: <path>
  roads_fc: <path>
  cell_size: 50
  study_buffer: 1500
  pop_field: null               # null = use field_mapping.population_count
  road_length_field: null

# ── GWR ──
gwr:
  dependent: "poi_count"
  explanatory: [pop_density, road_density]
  neighborhood_type: "NUMBER_OF_NEIGHBORS"   # or "DISTANCE_BAND"
  selection_method: "GOLDEN_SEARCH"          # or MANUAL_INTERVALS, USER_DEFINED
  min_neighbors: 30
  scale_data: true

# ── Prediction ──
prediction:
  prediction_fc: <path>
  explanatory: [pop_density, road_density]   # must match training fields

# ── Network (optional) ──
network:
  site_fc: <path>
  roads_fc: <path>
  pop_fc: <path>
  program_type: "Sports Centre"
  walkway_width: 3.0
  clip_buffer: 600
  gap_threshold: 1.4
```

## Troubleshooting

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `ERROR 110222: multicollinearity` | Variables too correlated; too few neighbors | Use `SCALE_DATA`; increase `min_neighbors`; remove correlated variables |
| `ERROR 000732: dataset not supported` | GPKG not supported by arcpy natively | Convert to shapefile/GDB first via `ogr2ogr` or geopandas |
| Field not found error | Column names don't match defaults | Set explicit field names in `field_mapping` section of config |
| Prediction fails with field mismatch | Prediction grid has different field names | Rename fields to match training data's explanatory variable names |
| `WARNING 110259: very limited variation` | Sparse data in some neighborhoods | Increase `number_of_neighbors`; check for identical-value clusters |

## Files

```
├── README.md
├── requirements.txt
├── config_template.json
├── .gitignore
└── scripts/
    ├── _utils.py                 # Shared field resolution utility
    ├── master_pipeline.py        # Run this
    ├── step1_classify_poi.py     # POI time classification
    ├── step2_pop_allocate.py     # Dasymetric population
    ├── step3_build_grid.py       # Grid + indicators
    ├── step4_gwr_model.py        # GWR fit + prediction
    └── step5_net_assign.py       # Network flow assignment
```

## Reference: Original Case Study

Validated against `Analysis_try6` notebooks (Tung Chung Bus Terminus, Hong Kong):

| Analysis | Key Metric | Original | ArcPy | Match |
|----------|-----------|----------|-------|-------|
| POI Classification | Total POIs | 1,184 | 1,184 | 100% |
| Dasymetric Population | Buildings | 598 | 598 | 100% |
| GWR Model | Local R² | 0.18 | 0.20 | Comparable |
| Network Assignment | Critical gaps | 1 | 1 | 100% |

## License

MIT
