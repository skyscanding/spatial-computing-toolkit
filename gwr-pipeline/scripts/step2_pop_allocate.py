"""
GWR Pipeline — Step 2: Dasymetric Population Allocation
=========================================================
Allocates census population to individual building footprints weighted by
building height (a proxy for GFA: gross floor area).

Formula: pop_bldg = census_pop × (footprint_area × height) / Σ(area × height)

Input:
  - pop_fc: str          — census population feature class (must have pop field)
  - bldg_fc: str          — building footprint feature class (must have elev field)
  - output_gdb: str       — output File Geodatabase
  - pop_field: str        — population count field name (default 'Averag_pop')
  - elev_field: str       — building elevation/height field (default 'Elevation')
  - fallback_height: float — height for buildings with missing data (default 3.0m)

Output (in output_gdb):
  - site_buildings         — buildings with 'bldg_pop' field (allocated population)
  - bldg_pop_intersect     — intermediate intersection fragments
  - bldg_pop_summary       — summary table

Usage:
  python step2_pop_allocate.py --config my_config.py
"""
import arcpy
import os, sys, json, time
import numpy as np

from _utils import resolve_field, with_default

FALLBACK_HEIGHT = 3.0
FLOOR_HEIGHT_M  = 3.0


def dasymetric_population(pop_fc, bldg_fc, output_gdb,
                           pop_field="Averag_pop",
                           elev_field="Elevation",
                           fallback_height=3.0,
                           arcpy_env=None):
    """
    Allocate census population to building footprints weighted by elevation.

    Parameters
    ----------
    pop_fc : str        — path to population polygon feature class
    bldg_fc : str       — path to building footprint feature class
    output_gdb : str    — path to output File Geodatabase
    pop_field : str     — field name containing population count
    elev_field : str    — field name containing building elevation (m)
    fallback_height : float — height for missing/zero elevation values
    arcpy_env : dict    — optional arcpy environment overrides
    """
    T0 = time.time()
    if arcpy_env:
        for k, v in arcpy_env.items():
            setattr(arcpy.env, k, v)
    arcpy.env.workspace = output_gdb
    arcpy.env.overwriteOutput = True

    # ═══════════ 1. Import data into GDB ═══════════
    print(f"  [{time.time()-T0:.0f}s] Importing data...")

    pop_gdb = os.path.join(output_gdb, "hk_population")
    if arcpy.Exists(pop_gdb):
        arcpy.management.Delete(pop_gdb)
    arcpy.conversion.FeatureClassToFeatureClass(pop_fc, output_gdb, "hk_population")
    print(f"    Population: {int(arcpy.management.GetCount(pop_gdb).getOutput(0))} features")

    bldg_gdb = os.path.join(output_gdb, "site_buildings")
    if arcpy.Exists(bldg_gdb):
        arcpy.management.Delete(bldg_gdb)
    arcpy.conversion.FeatureClassToFeatureClass(bldg_fc, output_gdb, "site_buildings")
    bldg_cnt = int(arcpy.management.GetCount(bldg_gdb).getOutput(0))
    print(f"    Buildings: {bldg_cnt} features")

    # ═══════════ 2. Prepare buildings (add Area, Elev, Volume fields) ═══════════
    print(f"  [{time.time()-T0:.0f}s] Preparing buildings...")

    bldg_flds = {f.name for f in arcpy.ListFields(bldg_gdb)}
    for fn in ["Area_m2","Elev_m","Volume","bldg_pop","est_floors"]:
        if fn not in bldg_flds:
            arcpy.management.AddField(bldg_gdb, fn, "DOUBLE")

    arcpy.management.CalculateField(bldg_gdb, "Area_m2",
        "!shape.area@squaremeters!", "PYTHON3")

    # Resolve elevation field name (explicit config → auto-detect → fail with message)
    try:
        actual_elev = resolve_field(bldg_gdb, elev_field, ["elevation", "elev", "height", "bldg_h", "z"])
    except ValueError as e:
        print(f"    WARNING: {e}. Using fallback height {fallback_height}m for all buildings.")
        actual_elev = None

    if actual_elev:
        code = f'''def get_elev(v):
    if v is None or v <= 0: return {fallback_height}
    return float(v)'''
        arcpy.management.CalculateField(bldg_gdb, "Elev_m",
            f"get_elev(!{actual_elev}!)", "PYTHON3", code)
    else:
        print(f"    WARNING: elevation field '{elev_field}' not found. Using {fallback_height}m")
        arcpy.management.CalculateField(bldg_gdb, "Elev_m", str(fallback_height), "PYTHON3")

    arcpy.management.CalculateField(bldg_gdb, "Volume", "!Area_m2! * !Elev_m!", "PYTHON3")
    arcpy.management.CalculateField(bldg_gdb, "est_floors", f"!Elev_m! / {FLOOR_HEIGHT_M}", "PYTHON3")

    areas, elevs = [], []
    with arcpy.da.SearchCursor(bldg_gdb, ["Area_m2","Elev_m"]) as cur:
        for row in cur:
            if row[0]: areas.append(row[0])
            if row[1]: elevs.append(row[1])
    print(f"    Footprint: {sum(areas):,.0f} m2  |  Elev: mean={np.mean(elevs):.1f}m  max={np.max(elevs):.1f}m")

    # ═══════════ 3. Spatial overlay: buildings × population polygons ═══════════
    print(f"  [{time.time()-T0:.0f}s] Intersecting buildings × population...")

    intersect_fc = os.path.join(output_gdb, "bldg_pop_intersect")
    if arcpy.Exists(intersect_fc):
        arcpy.management.Delete(intersect_fc)
    arcpy.analysis.Intersect([bldg_gdb, pop_gdb], intersect_fc, "ALL", None, "INPUT")
    frag_cnt = int(arcpy.management.GetCount(intersect_fc).getOutput(0))
    print(f"    Fragments: {frag_cnt}")

    # ═══════════ 4. Allocate population ═══════════
    print(f"  [{time.time()-T0:.0f}s] Allocating population (elevation-weighted)...")

    for fn in ["frag_area","frag_vol","frag_pop"]:
        if fn not in {f.name for f in arcpy.ListFields(intersect_fc)}:
            arcpy.management.AddField(intersect_fc, fn, "DOUBLE")

    arcpy.management.CalculateField(intersect_fc, "frag_area",
        "!shape.area@squaremeters!", "PYTHON3")
    arcpy.management.CalculateField(intersect_fc, "frag_vol",
        "!frag_area! * !Elev_m!", "PYTHON3")

    # Resolve identifier & population fields in intersect result
    # (after Intersect, field names get prefixed by source FC name)
    try:
        ssbg_fld = resolve_field(intersect_fc, None, ["ssbg", "census", "block_id", "zone"])
    except ValueError:
        ssbg_fld = None
        print("    WARNING: No census block ID field found in intersect result")

    try:
        pop_fld = resolve_field(intersect_fc, None, ["averag_pop", "pop", "t_pop", "total_pop"])
    except ValueError:
        pop_fld = None
        print("    WARNING: No population count field found in intersect result")

    if ssbg_fld and pop_fld:
        # Group volumes by census block
        block_vol = {}
        block_pop = {}
        with arcpy.da.SearchCursor(intersect_fc, [ssbg_fld, pop_fld, "frag_vol"]) as cur:
            for row in cur:
                bk = row[0]
                pv = float(row[1] or 0)
                vl = float(row[2] or 0)
                if bk not in block_vol:
                    block_vol[bk] = 0
                    block_pop[bk] = pv
                block_vol[bk] += vl

        # Allocate proportionally
        with arcpy.da.UpdateCursor(intersect_fc, [ssbg_fld, "frag_vol", "frag_pop"]) as cur:
            for row in cur:
                bk = row[0]
                vl = float(row[1] or 0)
                tv = block_vol.get(bk, 1)
                bp = block_pop.get(bk, 0)
                row[2] = bp * (vl / tv) if tv > 0 else 0
                cur.updateRow(row)
        print(f"    Allocated population to {frag_cnt} fragments")
    else:
        print(f"    WARNING: missing identifier/pop fields; cannot allocate")

    # ═══════════ 5. Summarize back to buildings ═══════════
    print(f"  [{time.time()-T0:.0f}s] Summarizing to buildings...")

    summary = os.path.join(output_gdb, "bldg_pop_summary")
    if arcpy.Exists(summary):
        arcpy.management.Delete(summary)

    try:
        bldg_id_fld = resolve_field(intersect_fc, None, ["fid_site", "fid_building", "building_id"])
    except ValueError:
        bldg_id_fld = "OBJECTID"
        print(f"    WARNING: No building FID field found; falling back to {bldg_id_fld}")

    try:
        arcpy.analysis.Statistics(intersect_fc, summary,
            [["frag_pop","SUM"]], bldg_id_fld)
        arcpy.management.JoinField(bldg_gdb, "OBJECTID", summary, bldg_id_fld, "SUM_frag_pop")
        for f in arcpy.ListFields(bldg_gdb):
            if f.name.startswith("SUM_frag"):
                arcpy.management.CalculateField(bldg_gdb, "bldg_pop", f"!{f.name}!", "PYTHON3")
                break
    except:
        # Fallback: cursor-based aggregation
        pop_dict = {}
        with arcpy.da.SearchCursor(intersect_fc, [bldg_id_fld, "frag_pop"]) as cur:
            for row in cur:
                bid = row[0]
                pop_dict[bid] = pop_dict.get(bid, 0) + float(row[1] or 0)
        with arcpy.da.UpdateCursor(bldg_gdb, ["OBJECTID","bldg_pop"]) as cur:
            for row in cur:
                row[1] = pop_dict.get(row[0]-1, 0)  # FID is 0-based
                cur.updateRow(row)

    total_pop = max_pop = 0
    with arcpy.da.SearchCursor(bldg_gdb, ["bldg_pop"]) as cur:
        for row in cur:
            if row[0]:
                total_pop += row[0]
                if row[0] > max_pop: max_pop = row[0]

    print(f"    Total pop (elev-weighted): {total_pop:,.0f}")
    print(f"    Max building pop: {max_pop:,.0f}")
    print(f"  DONE [{time.time()-T0:.0f}s]")
    return bldg_gdb


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--config", help="JSON config")
    p.add_argument("--pop-fc", help="Population feature class")
    p.add_argument("--bldg-fc", help="Building footprint feature class")
    p.add_argument("--output-gdb", help="Output GDB")
    p.add_argument("--pop-field", default="Averag_pop")
    p.add_argument("--elev-field", default="Elevation")
    p.add_argument("--fallback", type=float, default=3.0)
    args = p.parse_args()

    if args.config:
        with open(args.config,'r',encoding='utf-8') as f:
            cfg = json.load(f)
        for k in ['pop_fc','bldg_fc','output_gdb','pop_field','elev_field']:
            if k in cfg:
                setattr(args, k, cfg[k])
        if 'fallback_height' in cfg:
            args.fallback = cfg['fallback_height']

    dasymetric_population(args.pop_fc, args.bldg_fc, args.output_gdb,
                           args.pop_field, args.elev_field, args.fallback)
