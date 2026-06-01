# QGIS 空间分析操作手册

> QGIS 3.44 环境 | 安装路径 `D:\QGIS` | 含 298 原生算法 + GRASS 8.4 + SAGA + GDAL 3.11

---

## 目录

1. [环境启动](#环境启动)
2. [数据探查](#数据探查)
3. [坐标投影](#坐标投影)
4. [空间筛选与裁剪](#空间筛选与裁剪)
5. [几何操作](#几何操作)
6. [属性与字段](#属性与字段)
7. [空间连接与聚合](#空间连接与聚合)
8. [网络分析](#网络分析)
9. [网格与分区统计](#网格与分区统计)
10. [空间回归](#空间回归)
11. [数据导出](#数据导出)
12. [制图输出](#制图输出)
13. [工作流示例](#工作流示例)

---

## 环境启动

```bash
# qgis_process — QGIS 处理框架命令行（最常用）
D:\QGIS\bin\qgis_process-qgis.bat [command] [algorithm] [parameters]

# 带 QGIS Python 环境的解释器（用于 PyQGIS 脚本）
D:\QGIS\bin\python-qgis.bat script.py

# GDAL 矢量工具
D:\QGIS\bin\ogrinfo.exe    # 查看矢量信息
D:\QGIS\bin\ogr2ogr.exe    # 矢量转换/过滤

# GDAL 栅格工具
D:\QGIS\bin\gdalinfo.exe     # 查看栅格信息
D:\QGIS\bin\gdalwarp.exe     # 栅格重投影/裁剪
D:\QGIS\bin\gdal_translate.exe # 栅格格式转换
```

---

## 数据探查

### 查看 Shapefile

```bash
# 摘要信息（CRS、字段名和类型、几何类型、要素数）
"D:\QGIS\bin\ogrinfo.exe" data.shp -so

# 全部属性（含前 5 条记录的值）
"D:\QGIS\bin\ogrinfo.exe" data.shp -al -limit 5
```

### 查看 GeoPackage

```bash
# 列出图层
"D:\QGIS\bin\ogrinfo.exe" data.gpkg

# 查看指定图层
"D:\QGIS\bin\ogrinfo.exe" data.gpkg layer_name -so

# 查看图层属性 + 前 5 条
"D:\QGIS\bin\ogrinfo.exe" data.gpkg layer_name -al -limit 5
```

### 查看栅格

```bash
"D:\QGIS\bin\gdalinfo.exe" raster.tif
```

### GUI 方式

- 拖拽文件到 Layers 面板
- Browser Panel 展开 GPKG 看内部图层
- 右键图层 → Properties → Information
- 右键图层 → Open Attribute Table

---

## 坐标投影

### 矢量重投影

```bash
# qgis_process
"D:\QGIS\bin\qgis_process-qgis.bat" run native:reprojectlayer \
  --INPUT="input.shp" \
  --TARGET_CRS="EPSG:2326" \
  --OUTPUT="output_2326.gpkg"

# GDAL (更轻量，适合大文件)
"D:\QGIS\bin\ogr2ogr.exe" -t_srs EPSG:2326 output.shp input.shp
```

香港常用坐标系：
| EPSG | 名称 | 单位 |
|------|------|------|
| 4326 | WGS84 | 度 |
| 2326 | Hong Kong 1980 Grid | 米 |

### 栅格重投影

```bash
"D:\QGIS\bin\gdalwarp.exe" -t_srs EPSG:2326 output.tif input.tif
```

### 查看当前 CRS

```bash
"D:\QGIS\bin\ogrinfo.exe" data.shp -so | findstr "SRS"
"D:\QGIS\bin\gdalinfo.exe" raster.tif | findstr "SRS"
```

---

## 空间筛选与裁剪

### 按位置筛选（保留完整几何）

```bash
# 提取与 boundary 相交的所有要素
"D:\QGIS\bin\qgis_process-qgis.bat" run native:extractbylocation \
  --INPUT="all_features.gpkg" \
  --INTERSECT="boundary.shp" \
  --PREDICATE=intersects \
  --OUTPUT="filtered.gpkg"
```

PREDICATE 可选值：`intersects` | `contains` | `within` | `touches` | `crosses` | `overlaps` | `disjoint`

### 裁剪（修剪几何到边界内）

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:clip \
  --INPUT="all_features.gpkg" \
  --OVERLAY="boundary.shp" \
  --OUTPUT="clipped.gpkg"
```

### 按矩形范围筛选

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:extractbyextent \
  --INPUT="all_features.gpkg" \
  --EXTENT="811000,816000,813000,818000 [EPSG:2326]" \
  --OUTPUT="extent_subset.gpkg"
```

### 按属性表达式筛选

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:extractbyexpression \
  --INPUT="data.gpkg" \
  --EXPRESSION='"population" > 100 AND "district" = '\''TC'\''' \
  --OUTPUT="filtered.gpkg"
```

### 按几何类型筛选

```bash
# 仅保留线要素
"D:\QGIS\bin\qgis_process-qgis.bat" run native:filterbygeometry \
  --INPUT="mixed.gpkg" --LINES=true --POINTS=false --POLYGONS=false \
  --OUTPUT="lines_only.gpkg"
```

### GDAL 方式（适合超大文件，无需加载到内存）

```bash
# 按矩形范围筛选
"D:\QGIS\bin\ogr2ogr.exe" -spat 811000 816000 813000 818000 output.shp input.shp

# 按 SQL 条件筛选
"D:\QGIS\bin\ogr2ogr.exe" -where "population > 100" output.shp input.shp

# 裁剪到多边形边界
"D:\QGIS\bin\ogr2ogr.exe" -clipsrc boundary.shp output.shp input.shp
```

---

## 几何操作

### 缓冲区

```bash
# 单距离缓冲区
"D:\QGIS\bin\qgis_process-qgis.bat" run native:buffer \
  --INPUT="site.shp" --DISTANCE=600 --OUTPUT="site_600m.gpkg"

# 多环缓冲区（同时生成 200m, 600m, 1500m）
"D:\QGIS\bin\qgis_process-qgis.bat" run native:multiringconstantbuffer \
  --INPUT="site.shp" --RINGS="200,600,1500" --OUTPUT="multi_buf.gpkg"
```

### 融合（把多个面合并成一个面）

```bash
# 全部融合
"D:\QGIS\bin\qgis_process-qgis.bat" run native:dissolve \
  --INPUT="polygons.gpkg" --OUTPUT="merged.gpkg"

# 按字段分组融合
"D:\QGIS\bin\qgis_process-qgis.bat" run native:dissolve \
  --INPUT="polygons.gpkg" --FIELD="class" --OUTPUT="by_class.gpkg"
```

### 提取质心

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:centroids \
  --INPUT="polygons.gpkg" --OUTPUT="centroids.gpkg"
```

### 添加几何属性（面积/长度/周长）

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:exportaddgeometrycolumns \
  --INPUT="features.gpkg" --CALC_METHODS=0,1 --OUTPUT="with_geom.gpkg"
```
CALC_METHODS: 0=面积, 1=周长/长度, 2=质心X, 3=质心Y, 4=点X, 5=点Y

### 炸开与合并

```bash
# 多部件 → 单部件（MultiLineString → 逐段 LineString）
"D:\QGIS\bin\qgis_process-qgis.bat" run native:multiparttosingleparts \
  --INPUT="multipart.gpkg" --OUTPUT="single.gpkg"

# 单部件 → 多部件
"D:\QGIS\bin\qgis_process-qgis.bat" run native:promotetomulti \
  --INPUT="single.gpkg" --OUTPUT="multi.gpkg"

# 合并多个图层
"D:\QGIS\bin\qgis_process-qgis.bat" run native:mergevectorlayers \
  --LAYERS="layer_a.gpkg;layer_b.shp;layer_c.shp" --OUTPUT="merged.gpkg"
```

### 空间叠置分析

```bash
# 相交（取重叠部分）
"D:\QGIS\bin\qgis_process-qgis.bat" run native:intersection \
  --INPUT="layer_a.gpkg" --OVERLAY="layer_b.gpkg" --OUTPUT="intersection.gpkg"

# 差集（A 减去 B 重叠部分）
"D:\QGIS\bin\qgis_process-qgis.bat" run native:difference \
  --INPUT="layer_a.gpkg" --OVERLAY="layer_b.gpkg" --OUTPUT="difference.gpkg"

# 并集
"D:\QGIS\bin\qgis_process-qgis.bat" run native:union \
  --INPUT="layer_a.gpkg" --OVERLAY="layer_b.gpkg" --OUTPUT="union.gpkg"

# 对称差集（取不相交的部分）
"D:\QGIS\bin\qgis_process-qgis.bat" run native:symmetricaldifference \
  --INPUT="layer_a.gpkg" --OVERLAY="layer_b.gpkg" --OUTPUT="symdiff.gpkg"
```

### 其他常用几何操作

```bash
# 凸包
"D:\QGIS\bin\qgis_process-qgis.bat" run native:convexhull \
  --INPUT="points.gpkg" --OUTPUT="convex_hull.gpkg"

# 泰森多边形
"D:\QGIS\bin\qgis_process-qgis.bat" run native:voronoipolygons \
  --INPUT="points.gpkg" --BUFFER=200 --OUTPUT="voronoi.gpkg"

# 面转线
"D:\QGIS\bin\qgis_process-qgis.bat" run native:polygonstolines \
  --INPUT="polygons.gpkg" --OUTPUT="boundaries.gpkg"

# 简化几何
"D:\QGIS\bin\qgis_process-qgis.bat" run native:simplifygeometries \
  --INPUT="complex.gpkg" --METHOD=0 --TOLERANCE=5 --OUTPUT="simplified.gpkg"

# 修复无效几何
"D:\QGIS\bin\qgis_process-qgis.bat" run native:fixgeometries \
  --INPUT="broken.gpkg" --OUTPUT="fixed.gpkg"
```

---

## 属性与字段

### 字段计算器

这是 QGIS 最强大的属性操作入口。

**基本运算**：
```bash
# 新建数值字段
"D:\QGIS\bin\qgis_process-qgis.bat" run native:fieldcalculator \
  --INPUT="data.gpkg" \
  --FIELD_NAME="ratio" --FIELD_TYPE=0 \
  --FORMULA='"pop" * 1000 / "area"' \
  --OUTPUT="with_ratio.gpkg"

# 新建文本字段
"D:\QGIS\bin\qgis_process-qgis.bat" run native:fieldcalculator \
  --INPUT="data.gpkg" \
  --FIELD_NAME="label" --FIELD_TYPE=2 --FIELD_LENGTH=50 \
  --FORMULA="'\''Zone '\'' || \"zone_id\" || '\'': '\'' || round(\"pop\", 0)" \
  --OUTPUT="with_label.gpkg"
```

FIELD_TYPE: 0=Float, 1=Integer, 2=String

**条件分类（CASE WHEN）**：
```bash
# 数值分类：将 POI 按类型分为 3 类
"D:\QGIS\bin\qgis_process-qgis.bat" run native:fieldcalculator \
  --INPUT="poi.gpkg" \
  --FIELD_NAME="time_class" --FIELD_TYPE=1 \
  --FORMULA="CASE WHEN \"midType\" IN ('公司','银行','学校','培训机构','会展中心','科研机构') THEN 1 WHEN \"midType\" IN ('休闲餐饮场所','茶艺馆','冷饮店','休闲场所') THEN 2 ELSE 3 END" \
  --OUTPUT="poi_classified.gpkg"

# 文本分类：服务水平分级
"D:\QGIS\bin\qgis_process-qgis.bat" run native:fieldcalculator \
  --INPUT="edges.gpkg" \
  --FIELD_NAME="LOS" --FIELD_TYPE=2 --FIELD_LENGTH=1 \
  --FORMULA="CASE WHEN \"flow_pmpm\" >= 0.817 THEN 'E' WHEN \"flow_pmpm\" >= 0.550 THEN 'D' WHEN \"flow_pmpm\" >= 0.383 THEN 'C' ELSE 'B' END" \
  --OUTPUT="edges_los.gpkg"
```

**常用函数**：
```sql
-- 几何函数
$area               -- 面积
$length             -- 长度
$x                  -- 质心 X 坐标
$y                  -- 质心 Y 坐标
geom_to_wkt($geometry)  -- 转为 WKT 文本

-- 数学函数
abs("field")        -- 绝对值
round("field", 2)   -- 四舍五入
maximum("field")    -- 该字段全局最大值
minimum("field")    -- 该字段全局最小值
mean("field")       -- 该字段全局平均值

-- 文本函数
"a" || "b"          -- 字符串拼接
substr("name", 1, 5)  -- 截取子串
regexp_match("name", 'pattern')  -- 正则匹配

-- 空值处理
coalesce("field", 0)  -- 空值替换为 0
```

### 其他字段操作

```bash
# 删除字段
"D:\QGIS\bin\qgis_process-qgis.bat" run native:deletecolumn \
  --INPUT="data.gpkg" --COLUMN="unused" --OUTPUT="cleaned.gpkg"

# 重命名字段
"D:\QGIS\bin\qgis_process-qgis.bat" run native:renametablefield \
  --INPUT="data.gpkg" --FIELD="old_name" --NEW_NAME="new_name" --OUTPUT="renamed.gpkg"

# 只保留指定字段
"D:\QGIS\bin\qgis_process-qgis.bat" run native:retainfields \
  --INPUT="data.gpkg" --FIELDS="id;name;value" --OUTPUT="subset.gpkg"

# 添加自增 ID 字段
"D:\QGIS\bin\qgis_process-qgis.bat" run native:addautoincrementalfield \
  --INPUT="data.gpkg" --FIELD_NAME="uid" --OUTPUT="with_id.gpkg"

# 添加 X/Y 坐标字段
"D:\QGIS\bin\qgis_process-qgis.bat" run native:addxyfields \
  --INPUT="points.gpkg" --OUTPUT="with_xy.gpkg"

# 排序
"D:\QGIS\bin\qgis_process-qgis.bat" run native:orderbyexpression \
  --INPUT="data.gpkg" --EXPRESSION='"flow"' --ASCENDING=false --OUTPUT="sorted.gpkg"
```

---

## 空间连接与聚合

### 按字段值连接（类似 Excel VLOOKUP）

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:joinattributestable \
  --INPUT="main.gpkg" --FIELD="id" \
  --INPUT_2="lookup.gpkg" --FIELD_2="id" \
  --JOIN_FIELDS="name;category" \
  --OUTPUT="joined.gpkg"
```

### 按空间位置连接 + 汇总

```bash
# 统计每个多边形内有多少个点，以及点的属性汇总
"D:\QGIS\bin\qgis_process-qgis.bat" run native:joinbylocationsummary \
  --INPUT="polygons.gpkg" \
  --JOIN="points.gpkg" \
  --PREDICATE=intersects \
  --SUMMARIES=1,5 `# 1=count, 5=sum` \
  --JOIN_FIELDS="population" \
  --OUTPUT="spatial_join.gpkg"
```

SUMMARIES 可选值：1=count, 2=unique, 3=min, 4=max, 5=sum, 6=mean, 7=median, 8=stddev, 9=minority, 10=majority, 11=range, 12=q1, 13=q3, 14=iqr

### 按最近距离连接

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:joinbynearest \
  --INPUT="points.gpkg" \
  --INPUT_2="hubs.gpkg" \
  --NEIGHBORS=1 \
  --OUTPUT="nearest.gpkg"
```

### 聚合（Group By）

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:aggregate \
  --INPUT="data.gpkg" \
  --GROUP_FIELDS="district" \
  --AGGREGATES="1,5,6:population,6:area" \
  --OUTPUT="aggregated.gpkg"
```

AGGREGATES 格式：`聚合类型:字段名`，多个用逗号分隔。聚合类型同上 SUMMARIES。

### 计算多边形内点数

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:countpointsinpolygon \
  --POLYGONS="grid.gpkg" \
  --POINTS="poi.gpkg" \
  --CLASSWEIGHT="category" --FIELD="poi_count" \
  --OUTPUT="grid_with_counts.gpkg"
```

### 计算多边形内线长度

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:sumlinelengths \
  --INPUT="grid.gpkg" \
  --LINES="roads.gpkg" \
  --LEN_FIELD="road_length" --COUNT_FIELD="road_segments" \
  --OUTPUT="grid_road_density.gpkg"
```

---

## 网络分析

### 网络预处理

网络分析前需要确保线段端点正确连接：

```bash
# 1. 修复几何
"D:\QGIS\bin\qgis_process-qgis.bat" run native:fixgeometries \
  --INPUT="roads.gpkg" --OUTPUT="roads_fixed.gpkg"

# 2. 炸开多段线 → 单线段
"D:\QGIS\bin\qgis_process-qgis.bat" run native:explodelines \
  --INPUT="roads_fixed.gpkg" --OUTPUT="roads_exploded.gpkg"

# 3. 快照端点（连接间距 < 2m 的端点）
"D:\QGIS\bin\qgis_process-qgis.bat" run native:snapgeometries \
  --INPUT="roads_exploded.gpkg" \
  --REFERENCE_LAYER="roads_exploded.gpkg" \
  --TOLERANCE=2 --BEHAVIOR=3 \
  --OUTPUT="roads_snapped.gpkg"
```

### 点到点最短路径

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:shortestpathpointtopoint \
  --INPUT="roads_snapped.gpkg" \
  --STRATEGY=0 \
  --START_POINT="811700,816900 [EPSG:2326]" \
  --END_POINT="812500,817500 [EPSG:2326]" \
  --OUTPUT="shortest_path.gpkg"
```
STRATEGY: 0=最短距离, 1=最快路径

### 图层到点最短路径（批量起点 → 单个终点）

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:shortestpathlayertopoint \
  --INPUT="roads_snapped.gpkg" \
  --STRATEGY=0 \
  --START_POINTS="origins.gpkg" \
  --END_POINT="812500,817500 [EPSG:2326]" \
  --OUTPUT="paths.gpkg"
```

### 服务区（等时圈）

```bash
# 从单点出发，计算 5/10/15 分钟步行范围
"D:\QGIS\bin\qgis_process-qgis.bat" run native:serviceareafrompoint \
  --INPUT="roads_snapped.gpkg" \
  --STRATEGY=1 \
  --START_POINT="811700,816900 [EPSG:2326]" \
  --TRAVEL_COST="300,600,900" \
  --OUTPUT="service_area.gpkg"
```
TRAVEL_COST 单位取决于边的权重字段：若边权重为长度（米）则填米，若为时间（秒）则填秒。

### 从图层出发的服务区

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:serviceareafromlayer \
  --INPUT="roads_snapped.gpkg" \
  --STRATEGY=1 \
  --START_POINTS="facilities.gpkg" \
  --TRAVEL_COST="300,600,900" \
  --OUTPUT="multi_service_area.gpkg"
```

### 流量分配（网络流累加）

QGIS 原生工具只能计算**单条最短路径**，无法做到**多条 OD 对的流量在同一路段上累加**。

如果需要对每条路段累加来自多个出发点的流量（例如：100 个居民区 → 1 个目的地的所有最短路径叠加），需要使用 PyQGIS 编写自定义脚本。基本思路：

```
qgis_process 预处理（缓冲/裁剪/网络准备）
    ↓
networkx 读取道路构建图
    ↓
批量计算最短路径 + 累加路段流量
    ↓
qgis_process 后处理（LOS 分级/导出）
```

完整脚本见[工作流示例 — 网络流分配](#示例-3网络流分配pyqgis-脚本)。

---

## 网格与分区统计

### 创建网格

```bash
# 矩形网格 50m × 50m
"D:\QGIS\bin\qgis_process-qgis.bat" run native:creategrid \
  --TYPE=2 --EXTENT="810800,816000,813800,819000 [EPSG:2326]" \
  --HSPACING=50 --VSPACING=50 \
  --OUTPUT="grid_50m.gpkg"

# 六边形网格 100m
"D:\QGIS\bin\qgis_process-qgis.bat" run native:creategrid \
  --TYPE=4 --EXTENT="810800,816000,813800,819000 [EPSG:2326]" \
  --HSPACING=100 \
  --OUTPUT="hex_grid.gpkg"
```
TYPE: 0=点, 1=线, 2=矩形, 3=菱形, 4=六边形

### 分区统计（从栅格提取值到矢量面）

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:zonalstatisticsfb \
  --INPUT="zones.gpkg" \
  --RASTER="population.tif" \
  --COLUMN_PREFIX="pop_" \
  --STATISTICS="1,2,4,5,6" \
  --OUTPUT="zones_with_stats.gpkg"
```
STATISTICS: 1=Count, 2=Sum, 3=Minority, 4=Mean, 5=Stddev, 6=Min, 7=Max, 8=Range, 9=Median, 10=Majority

### 栅格采样（提取点到栅格值）

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:rastersampling \
  --INPUT="points.gpkg" \
  --RASTERCOPY="elevation.tif" \
  --COLUMN_PREFIX="dem_" \
  --OUTPUT="points_with_elev.gpkg"
```

### 栅格像素转矢量

```bash
# 转点
"D:\QGIS\bin\qgis_process-qgis.bat" run native:pixelstopoints \
  --INPUT="raster.tif" --OUTPUT="raster_points.gpkg"

# 转面
"D:\QGIS\bin\qgis_process-qgis.bat" run native:pixelstopolygons \
  --INPUT="raster.tif" --OUTPUT="raster_polygons.gpkg"
```

---

## 空间回归

### GWR 地理加权回归（SAGA）

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

### 其他统计方法

```bash
# 基本统计（字段的 count/mean/std/min/max 等）
"D:\QGIS\bin\qgis_process-qgis.bat" run native:basicstatisticsforfields \
  --INPUT="data.gpkg" --FIELD_NAMES="pop;area;ratio" --OUTPUT="stats.html"

# 最近邻分析（判断点分布的聚集程度）
"D:\QGIS\bin\qgis_process-qgis.bat" run native:nearestneighbouranalysis \
  --INPUT="points.gpkg" --OUTPUT="nn_analysis.html"

# K-means 聚类
"D:\QGIS\bin\qgis_process-qgis.bat" run native:kmeansclustering \
  --INPUT="data.gpkg" --CLUSTERS=5 --FIELDS="x;y;value" --OUTPUT="clusters.gpkg"

# DBSCAN 聚类（基于密度的聚类）
"D:\QGIS\bin\qgis_process-qgis.bat" run native:dbscanclustering \
  --INPUT="points.gpkg" --MIN_SIZE=5 --EPS=100 --OUTPUT="dbscan.gpkg"
```

---

## 数据导出

### 保存矢量图层

```bash
# 保存为 GPKG
"D:\QGIS\bin\qgis_process-qgis.bat" run native:savefeatures \
  --INPUT="processed.gpkg" \
  --LAYER_NAME="my_layer" \
  --OUTPUT="final.gpkg"

# 保存为 Shapefile
"D:\QGIS\bin\qgis_process-qgis.bat" run native:savefeatures \
  --INPUT="processed.gpkg" --OUTPUT="final.shp"

# 导出选中要素
"D:\QGIS\bin\qgis_process-qgis.bat" run native:saveselectedfeatures \
  --INPUT="data.gpkg" --OUTPUT="selected_only.gpkg"
```

### 导出为表格

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:exporttospreadsheet \
  --INPUT="data.gpkg" --OUTPUT="output.xlsx"
```

### ogr2ogr 方式 — 创建多图层 GPKG

```bash
# 第一层
"D:\QGIS\bin\ogr2ogr.exe" -f GPKG output.gpkg layer_a.shp -nln layer_a

# 追加第二层
"D:\QGIS\bin\ogr2ogr.exe" -f GPKG -update output.gpkg layer_b.shp -nln layer_b

# 追加第三层（带坐标系转换）
"D:\QGIS\bin\ogr2ogr.exe" -f GPKG -update -t_srs EPSG:2326 output.gpkg layer_c.shp -nln layer_c
```

### 导出 DXF（CAD 格式）

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:dxfexport \
  --LAYERS="roads.gpkg;buildings.shp" \
  --SYMBOLOGY_MODE=0 --SYMBOLOGY_SCALE=1000 \
  --OUTPUT="export.dxf"
```

---

## 制图输出

### Print Layout 导出（需在 QGIS 工程中预先配置布局）

```bash
# 导出为图片
"D:\QGIS\bin\qgis_process-qgis.bat" run native:printlayouttoimage \
  --LAYOUT="my_layout" --DPI=300 --OUTPUT="map.png"

# 导出为 PDF
"D:\QGIS\bin\qgis_process-qgis.bat" run native:printlayouttopdf \
  --LAYOUT="my_layout" --DPI=300 --OUTPUT="map.pdf"

# 如果布局在指定工程文件中，加上 PROJECT_PATH
"D:\QGIS\bin\qgis_process-qgis.bat" run native:printlayouttoimage \
  --PROJECT_PATH="project.qgz" --LAYOUT="my_layout" --DPI=250 \
  --OUTPUT="output.png"
```

### 图集批量导出

```bash
"D:\QGIS\bin\qgis_process-qgis.bat" run native:atlaslayouttopdf \
  --LAYOUT="atlas" --COVERAGE_LAYER="grid.gpkg" --DPI=200 \
  --OUTPUT="atlas_output.pdf"
```

### GUI 方式（推荐用于制图）

`Project → New Print Layout` 可在 GIS 窗口中交互式设计地图：
- **Add Map** — 添加地图窗口，选择显示的图层
- **Add Legend** — 自动生成图例
- **Add Scale Bar** — 比例尺
- **Add Label** — 标题和标注
- **Layer Styling Panel** — 为每个图层配置样式：
  - Single Symbol — 统一样式
  - Categorized — 按字段值分色（如：用地类型）
  - Graduated — 按数值渐变（如：人口密度、流量）
  - Rule-based — 复杂条件样式

---

## 工作流示例

### 示例 1：空间数据预处理管道

完整操作链：加载场地 → 缓冲区 → 裁剪道路 → 筛选人口 → 字段计算

```bash
#!/bin/bash
SITE="D:/data/Designsite.shp"
ROADS="D:/data/roads.gpkg"
POP="D:/data/population.gpkg"
OUT="D:/output"
mkdir -p "$OUT"

# Step 1: 600m 缓冲区
"D:\QGIS\bin\qgis_process-qgis.bat" run native:buffer \
  --INPUT="$SITE" --DISTANCE=600 --OUTPUT="$OUT/site_buf600.gpkg"

# Step 2: 裁剪道路
"D:\QGIS\bin\qgis_process-qgis.bat" run native:clip \
  --INPUT="$ROADS" --OVERLAY="$OUT/site_buf600.gpkg" --OUTPUT="$OUT/roads_clip.gpkg"

# Step 3: 筛选缓冲区范围内人口
"D:\QGIS\bin\qgis_process-qgis.bat" run native:extractbylocation \
  --INPUT="$POP" --INTERSECT="$OUT/site_buf600.gpkg" --PREDICATE=intersects \
  --OUTPUT="$OUT/pop_600m.gpkg"

# Step 4: 添加道路长度字段
"D:\QGIS\bin\qgis_process-qgis.bat" run native:exportaddgeometrycolumns \
  --INPUT="$OUT/roads_clip.gpkg" --CALC_METHODS=0 --OUTPUT="$OUT/roads_len.gpkg"

# Step 5: 计算人口 trips（每人 0.5 次出行）
"D:\QGIS\bin\qgis_process-qgis.bat" run native:fieldcalculator \
  --INPUT="$OUT/pop_600m.gpkg" --FIELD_NAME="trips" --FIELD_TYPE=0 \
  --FORMULA='"Averag_pop" * 0.5' --OUTPUT="$OUT/pop_trips.gpkg"

echo "完成。输出: $OUT"
```

### 示例 2：POI 分类 + 网格统计

完整操作链：POI 时段分类 → 创建网格 → 统计各类 POI 数量

```bash
#!/bin/bash
POI="D:/data/all_poi.gpkg"
EXTENT="810800,816000,813800,819000 [EPSG:2326]"
OUT="D:/output"
mkdir -p "$OUT"

# Step 1: POI 时段分类（字段计算器 CASE WHEN）
"D:\QGIS\bin\qgis_process-qgis.bat" run native:fieldcalculator \
  --INPUT="$POI" --FIELD_NAME="time_class" --FIELD_TYPE=1 \
  --FORMULA="CASE WHEN \"midType\" IN ('公司','银行','学校','培训机构','科研机构','会展中心') THEN 1 WHEN \"midType\" IN ('休闲餐饮场所','茶艺馆','冷饮店','休闲场所') THEN 2 ELSE 3 END" \
  --OUTPUT="$OUT/poi_classified.gpkg"

# Step 2: 创建 50m 网格
"D:\QGIS\bin\qgis_process-qgis.bat" run native:creategrid \
  --TYPE=2 --EXTENT="$EXTENT" --HSPACING=50 --VSPACING=50 --OUTPUT="$OUT/grid.gpkg"

# Step 3: 按类别分别统计
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

echo "完成。输出: $OUT/grid_t*.gpkg"
```

### 示例 3：网络流分配（PyQGIS 脚本）

以下脚本用 qgis_process 做数据前后处理，用 networkx 做核心最短路径流量分配。
保存为 `flow_assignment.py`，用 `D:\QGIS\bin\python-qgis.bat flow_assignment.py` 运行。

```python
"""
网络流分配 — 多出发地 → 单一目的地最短路径流量累加
运行方式: D:\QGIS\bin\python-qgis.bat flow_assignment.py
"""
import os, sys
import processing
import networkx as nx
import numpy as np
from shapely.geometry import Point, LineString
from shapely.ops import nearest_points
from qgis.core import QgsVectorLayer, QgsFeature, QgsGeometry, QgsField, QgsFields
from qgis.PyQt.QtCore import QVariant

# ═══════════ 配置 ═══════════
SITE_PATH  = r"D:/data/Designsite.shp"
ROADS_PATH = r"D:/data/roads.gpkg"
POP_PATH   = r"D:/data/population.gpkg"
OUT_DIR    = r"D:/output"
BUFFER_M   = 600
WALK_SPEED = 1.25   # m/s
MAX_WALK_M = 2000   # 最大步行距离
TRIP_RATE  = 0.5    # 人均出行率

os.makedirs(OUT_DIR, exist_ok=True)

# ═══════════ Phase 1: qgis_process 预处理 ═══════════
print("[1/4] 预处理...")

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

# ═══════════ Phase 2: networkx 构建图 ═══════════
print("[2/4] 构建网络图...")

roads_layer = QgsVectorLayer(roads_exp, "roads", "ogr")
site_layer  = QgsVectorLayer(SITE_PATH, "site", "ogr")

G = nx.Graph()
node_coords = {}
coord_to_node = {}
next_node_id = 0
SNAP = 2.0  # 节点快照容差

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

print(f"  节点: {G.number_of_nodes()}, 边: {G.number_of_edges()}")

# ═══════════ Phase 3: 最短路径 + 流量累加 ═══════════
print("[3/4] 流量分配...")

# 获取场地质心 → 最近节点
site_centroid = site_layer.getFeature(1).geometry().centroid()
site_xy = (site_centroid.asPoint().x(), site_centroid.asPoint().y())

graph_nodes = list(G.nodes())
graph_xy = np.array([node_coords[n] for n in graph_nodes])
from scipy.spatial import cKDTree
tree = cKDTree(graph_xy)
_, idx = tree.query(site_xy)
dest_node = graph_nodes[idx]

# Dijkstra — 所有节点到目的地的最短距离
sp_dist = nx.single_source_dijkstra_path_length(G, dest_node, weight='weight')
print(f"  可达节点: {len(sp_dist)} / {G.number_of_nodes()}")

# 流量累加
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

print(f"  分配: {assigned} 起点, 跳过: {skipped}, 总流量: {total_trips:.0f}")

# ═══════════ Phase 4: 写回 + LOS 分级 ═══════════
print("[4/4] 导出结果...")

# 将流量值写入道路图层（通过 virtal field 或复制图层）
# ...（省略详细的 QgsVectorFileWriter 写入代码，实际使用 qgis_process downstream）

# LOS 分级
processing.run("native:fieldcalculator", {
    'INPUT': f'{OUT_DIR}/roads_with_flow.gpkg',
    'FIELD_NAME': 'LOS', 'FIELD_TYPE': 2, 'FIELD_LENGTH': 3,
    'FORMULA': "CASE WHEN \"flow_pmpm\" >= 0.817 THEN 'E' WHEN \"flow_pmpm\" >= 0.550 THEN 'D' WHEN \"flow_pmpm\" >= 0.383 THEN 'C' ELSE 'B' END",
    'OUTPUT': f'{OUT_DIR}/final.gpkg'
})

print(f"完成 → {OUT_DIR}/final.gpkg")
```

### 示例 4：GWR 预测管道

完整操作链：创建网格 → 空间统计 → GWR 回归 → 预测

```bash
#!/bin/bash
EXTENT="810800,816000,813800,819000 [EPSG:2326]"
OUT="D:/output"
mkdir -p "$OUT"

# Step 1: 创建 50m 网格
"D:\QGIS\bin\qgis_process-qgis.bat" run native:creategrid \
  --TYPE=2 --EXTENT="$EXTENT" --HSPACING=50 --VSPACING=50 \
  --OUTPUT="$OUT/grid.gpkg"

# Step 2: 统计网格内 POI 数量
"D:\QGIS\bin\qgis_process-qgis.bat" run native:countpointsinpolygon \
  --POLYGONS="$OUT/grid.gpkg" --POINTS="poi.gpkg" \
  --FIELD="poi_count" --OUTPUT="$OUT/grid_poi.gpkg"

# Step 3: 统计网格内道路密度
"D:\QGIS\bin\qgis_process-qgis.bat" run native:sumlinelengths \
  --INPUT="$OUT/grid_poi.gpkg" --LINES="roads.gpkg" \
  --LEN_FIELD="road_len" --COUNT_FIELD="road_n" \
  --OUTPUT="$OUT/grid_poi_road.gpkg"

# Step 4: 分区统计 — 从人口栅格提取值
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

echo "完成。GWR 结果: $OUT/gwr_*.gpkg"
```

---

## 常见问题

### GPKG 比 SHP 好在哪？

- GPKG 是单一文件，不像 SHP 需要 .shp + .shx + .dbf + .prj 四个文件
- 支持多个图层存入一个文件
- 字段名长度无限制（SHP 限制 10 字符）
- 支持更多数据类型（日期、布尔、BLOB）
- 建议：中间过程用 GPKG，最终交付视需求选 SHP

### 中文路径/中文字段名能正常用吗？

- GPKG 和 Shapefile 均支持中文字段名和中文路径
- 但 GDAL 命令行工具对中文路径的引号处理较敏感，建议使用英文路径，或将中文路径放入变量中

### qgis_process 管道化

qgis_process 每个 `run` 命令是独立进程。要做管道，需要将每步输出保存为文件作为下一步输入：

```bash
# 不要这样（不支持）:
qgis_process run buffer | qgis_process run clip   # 无效！

# 这样做:
qgis_process run buffer --OUTPUT="temp.gpkg"
qgis_process run clip --INPUT="temp.gpkg" --OUTPUT="final.gpkg"
```

可用 Model Builder（`Processing → Graphical Modeler`）将管道保存为 .model3 文件，之后用 `qgis_process run model:your_model` 一键执行整条管道。

### 如何知道有哪些可用算法？

```bash
# 列出所有算法
"D:\QGIS\bin\qgis_process-qgis.bat" list

# 只看 native 算法
"D:\QGIS\bin\qgis_process-qgis.bat" list | findstr "native:"

# 看某个算法的参数说明
"D:\QGIS\bin\qgis_process-qgis.bat" help native:buffer
```
