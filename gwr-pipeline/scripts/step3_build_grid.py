"""
GWR Pipeline — Step 3: Grid Creation + Indicator Spatial Join
===============================================================
Creates a fishnet grid over the study area and computes built-environment
indicators per grid cell: POI count, population density, road density.

Input:
  - site_fc: str           — site boundary feature class
  - poi_fc: str            — POI feature class
  - pop_fc: str            — population feature class
  - roads_fc: str          — road network feature class
  - output_gdb: str        — output GDB
  - cell_size: float        — grid cell size in metres (default 50)
  - study_buffer: float     — buffer distance around site (default 1500m)
  - pop_field: str          — population count field
  - road_length_field: str  — road segment length field (e.g. 'Shape_Leng')
  - crs: str                — spatial reference (e.g. 'EPSG:2326')

Output (in output_gdb):
  - grid_indicators_full    — grid FC with poi_count, pop_density, road_density
  - grid_active_cells       — subset where poi_count > 0
  - study_area_<N>m         — buffer polygon defining study extent

Usage:
  python step3_build_grid.py --config my_config.py
"""
import arcpy
import os, sys, json, time
import numpy as np

from _utils import resolve_field, with_default


def build_indicator_grid(site_fc, poi_fc, pop_fc, roads_fc, output_gdb,
                          cell_size=50, study_buffer=1500,
                          pop_field="Averag_pop",
                          road_length_field="Shape_Leng",
                          crs="EPSG:2326",
                          arcpy_env=None):
    """
    Create fishnet grid + join indicators for GWR modeling.

    Returns (grid_full, grid_active) paths.
    """
    T0 = time.time()
    if arcpy_env:
        for k, v in arcpy_env.items():
            setattr(arcpy.env, k, v)
    arcpy.env.workspace = output_gdb
    arcpy.env.overwriteOutput = True

    # ═══════════ 1. Site + study area ═══════════
    print(f"  [{time.time()-T0:.0f}s] Defining study area...")

    site_gdb = os.path.join(output_gdb, "design_site")
    if arcpy.Exists(site_gdb):
        arcpy.management.Delete(site_gdb)
    arcpy.conversion.FeatureClassToFeatureClass(site_fc, output_gdb, "design_site")

    # Site centroid & area
    with arcpy.da.SearchCursor(site_gdb, ["SHAPE@AREA","SHAPE@XY"]) as cur:
        for row in cur:
            print(f"    Site area: {row[0]/10000:.2f} ha, centroid: E{row[1][0]:.0f} N{row[1][1]:.0f}")
            break

    study_fc = os.path.join(output_gdb, f"study_area_{study_buffer}m")
    if arcpy.Exists(study_fc):
        arcpy.management.Delete(study_fc)
    arcpy.analysis.Buffer(site_gdb, study_fc, f"{study_buffer} Meters")

    # ═══════════ 2. Create fishnet grid ═══════════
    print(f"  [{time.time()-T0:.0f}s] Creating {cell_size}m fishnet grid...")

    desc = arcpy.da.Describe(study_fc)
    ext = desc["extent"]
    origin = f"{ext.XMin} {ext.YMin}"
    opp_corner = f"{ext.XMax} {ext.YMax}"
    y_axis = f"{ext.XMin} {ext.YMin + cell_size}"

    grid_fc = os.path.join(output_gdb, "grid_raw")
    if arcpy.Exists(grid_fc):
        arcpy.management.Delete(grid_fc)

    arcpy.management.CreateFishnet(
        grid_fc, origin, y_axis,
        cell_size, cell_size, None, None,
        opp_corner, "NO_LABELS", study_fc, "POLYGON"
    )
    grid_cnt = int(arcpy.management.GetCount(grid_fc).getOutput(0))
    print(f"    Grid cells: {grid_cnt}")

    # Add cell area
    arcpy.management.AddField(grid_fc, "cell_area", "DOUBLE")
    arcpy.management.CalculateField(grid_fc, "cell_area", "!shape.area@squaremeters!", "PYTHON3")

    # ═══════════ 3. POI count per grid cell ═══════════
    print(f"  [{time.time()-T0:.0f}s] Spatial join: POI count...")

    grid_poi = os.path.join(output_gdb, "grid_poi_join")
    if arcpy.Exists(grid_poi):
        arcpy.management.Delete(grid_poi)
    arcpy.analysis.SpatialJoin(grid_fc, poi_fc, grid_poi,
        "JOIN_ONE_TO_ONE", "KEEP_ALL", match_option="INTERSECT")

    # Copy Join_Count → poi_count
    arcpy.management.AddField(grid_poi, "poi_count", "LONG")
    for f in arcpy.ListFields(grid_poi):
        if f.name == "Join_Count":
            arcpy.management.CalculateField(grid_poi, "poi_count", "!Join_Count!", "PYTHON3")
            break

    poi_total = poi_cells = 0
    with arcpy.da.SearchCursor(grid_poi, ["poi_count"]) as cur:
        for row in cur:
            if row[0] and row[0] > 0:
                poi_total += row[0]
                poi_cells += 1
    print(f"    POI total: {poi_total}, cells with POI: {poi_cells}")

    # ═══════════ 4. Population density per grid cell ═══════════
    print(f"  [{time.time()-T0:.0f}s] Spatial join: population density...")

    grid_pop_tmp = os.path.join(output_gdb, "grid_pop_tmp")
    if arcpy.Exists(grid_pop_tmp):
        arcpy.management.Delete(grid_pop_tmp)

    arcpy.analysis.SpatialJoin(grid_poi, pop_fc, grid_pop_tmp,
        "JOIN_ONE_TO_ONE", "KEEP_ALL", match_option="INTERSECT")

    # Resolve population field in join result (explicit config → auto-detect)
    try:
        pop_fld_name = resolve_field(grid_pop_tmp, pop_field, ["averag_pop", "pop", "t_pop", "a_po"])
    except ValueError:
        pop_fld_name = None
        print(f"    WARNING: Cannot find population field in spatial join result")

    arcpy.management.AddField(grid_poi, "pop_density", "DOUBLE")

    if pop_fld_name:
        arcpy.management.JoinField(grid_poi, "OBJECTID", grid_pop_tmp, "TARGET_FID", pop_fld_name)
        code = f'''def density(p, a):
    if p is None or a is None or a <= 0: return 0
    return p / (a / 10000)'''
        arcpy.management.CalculateField(grid_poi, "pop_density",
            f"density(!{pop_fld_name}!, !cell_area!)", "PYTHON3", code)

    arcpy.management.Delete(grid_pop_tmp)

    # ═══════════ 5. Road density per grid cell ═══════════
    print(f"  [{time.time()-T0:.0f}s] Spatial join: road density...")

    # Clip roads to study area
    roads_clip = os.path.join(output_gdb, "roads_study_area")
    if arcpy.Exists(roads_clip):
        arcpy.management.Delete(roads_clip)
    arcpy.analysis.Clip(roads_fc, study_fc, roads_clip)
    road_cnt = int(arcpy.management.GetCount(roads_clip).getOutput(0))
    print(f"    Roads in study area: {road_cnt}")

    grid_road_tmp = os.path.join(output_gdb, "grid_road_tmp")
    if arcpy.Exists(grid_road_tmp):
        arcpy.management.Delete(grid_road_tmp)

    arcpy.analysis.SpatialJoin(grid_poi, roads_clip, grid_road_tmp,
        "JOIN_ONE_TO_ONE", "KEEP_ALL", match_option="INTERSECT")

    arcpy.management.AddField(grid_poi, "road_density", "DOUBLE")

    # Resolve road length field (explicit config → auto-detect)
    try:
        rl_fld = resolve_field(grid_road_tmp, road_length_field, ["shape_leng", "length", "road_len", "segment_len"])
    except ValueError:
        rl_fld = None
        print("    WARNING: Cannot find road length field in spatial join result")

    if rl_fld:
        # Summarize total road length per grid cell
        road_sum = os.path.join(output_gdb, "road_len_summary")
        if arcpy.Exists(road_sum):
            arcpy.management.Delete(road_sum)
        try:
            arcpy.analysis.Statistics(grid_road_tmp, road_sum,
                [[rl_fld, "SUM"]], "TARGET_FID")
            arcpy.management.JoinField(grid_poi, "OBJECTID", road_sum, "TARGET_FID",
                                       f"SUM_{rl_fld}")
            sum_field = f"SUM_{rl_fld}"
            code = f'''def rd(l, a):
    if l is None or a is None or a <= 0: return 0
    return l / a'''
            arcpy.management.CalculateField(grid_poi, "road_density",
                f"rd(!{sum_field}!, !cell_area!)", "PYTHON3", code)
        except:
            print("    Road density: summarization failed; using Join_Count as proxy")
    else:
        print(f"    WARNING: road length field '{road_length_field}' not found")

    arcpy.management.Delete(grid_road_tmp)

    # ═══════════ 6. Filter active cells ═══════════
    print(f"  [{time.time()-T0:.0f}s] Filtering active cells (POI > 0)...")

    grid_full = os.path.join(output_gdb, "grid_indicators_full")
    if arcpy.Exists(grid_full):
        arcpy.management.Delete(grid_full)
    arcpy.management.CopyFeatures(grid_poi, grid_full)

    grid_active = os.path.join(output_gdb, "grid_active_cells")
    if arcpy.Exists(grid_active):
        arcpy.management.Delete(grid_active)
    arcpy.analysis.Select(grid_full, grid_active, "poi_count > 0")

    active_cnt = int(arcpy.management.GetCount(grid_active).getOutput(0))
    print(f"    Active cells: {active_cnt} / {grid_cnt}")

    # Print summary stats
    for var in ["poi_count","pop_density","road_density"]:
        vals = [r[0] for r in arcpy.da.SearchCursor(grid_active, [var]) if r[0] is not None]
        if vals:
            print(f"    {var}: mean={np.mean(vals):.3f} max={np.max(vals):.1f}")

    print(f"  DONE [{time.time()-T0:.0f}s]")
    return grid_full, grid_active


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--config", help="JSON config")
    p.add_argument("--site-fc", help="Site boundary FC")
    p.add_argument("--poi-fc", help="POI feature class")
    p.add_argument("--pop-fc", help="Population FC")
    p.add_argument("--roads-fc", help="Road network FC")
    p.add_argument("--output-gdb", help="Output GDB")
    p.add_argument("--cell-size", type=float, default=50)
    p.add_argument("--study-buffer", type=float, default=1500)
    p.add_argument("--pop-field", default="Averag_pop")
    p.add_argument("--road-length-field", default="Shape_Leng")
    p.add_argument("--crs", default="EPSG:2326")
    args = p.parse_args()

    if args.config:
        with open(args.config,'r',encoding='utf-8') as f:
            cfg = json.load(f)
        for k in ['site_fc','poi_fc','pop_fc','roads_fc','output_gdb',
                   'cell_size','study_buffer','pop_field','road_length_field','crs']:
            if k in cfg:
                setattr(args, k, cfg[k])

    build_indicator_grid(args.site_fc, args.poi_fc, args.pop_fc, args.roads_fc,
                          args.output_gdb, args.cell_size, args.study_buffer,
                          args.pop_field, args.road_length_field, args.crs)
