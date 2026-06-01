"""
GWR Pipeline — Step 5 (Supplementary): Pedestrian Network Flow Assignment
===========================================================================
Builds a pedestrian graph from road network and distributes trips from
population origins to a destination using shortest-path routing.
Computes LOS (Level of Service) and detects connectivity gaps.

This step is supplementary to the GWR pipeline — it provides the human-scale
pedestrian flow context that complements the grid-level GWR prediction.

Dependencies: networkx, scipy, shapely (install if missing)

Input:
  - site_fc: str            — destination site boundary FC
  - roads_fc: str           — road/pedestrian network FC
  - pop_fc: str             — population origins FC
  - output_gdb: str         — output GDB
  - pop_field: str           — population count field
  - program_type: str        — land-use program (for trip generation rate)
  - walkway_width: float     — effective walkway width (m)
  - clip_buffer: float       — buffer distance around site for network (m)
  - gap_threshold: float     — detour ratio above which a gap is flagged

Output (in output_gdb):
  - link_loads_200m          — loaded edges within 200m of site with LOS
  - gap_zones                — straight-line connections showing gaps
  - site_buf200 / site_buf600 — buffer polygons

Usage:
  python step5_net_assign.py --config my_config.py
"""
import arcpy
import os, sys, json, time
import numpy as np

from _utils import resolve_field, with_default

T0 = time.time()


def network_flow_assignment(site_fc, roads_fc, pop_fc, output_gdb,
                             pop_field="Averag_pop",
                             road_length_field=None,
                             road_travel_time_field=None,
                             program_type="Sports Centre",
                             walkway_width=3.0,
                             clip_buffer=600,
                             gap_threshold=1.4,
                             crs="EPSG:2326",
                             arcpy_env=None):
    """
    Run pedestrian network flow assignment.
    Returns (link_loads_fc, gap_zones_fc) paths.
    """
    # Ensure packages
    try:
        import networkx as nx
        from scipy.spatial import cKDTree
        from shapely.geometry import Point, LineString
        from shapely import wkt as shapely_wkt
    except ImportError:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-q",
                               "networkx", "scipy", "shapely"])
        import networkx as nx
        from scipy.spatial import cKDTree
        from shapely.geometry import Point, LineString
        from shapely import wkt as shapely_wkt

    if arcpy_env:
        for k, v in arcpy_env.items():
            setattr(arcpy.env, k, v)
    arcpy.env.workspace = output_gdb
    arcpy.env.overwriteOutput = True

    # Trip generation rates per 100m2 GFA
    TPDM_RATES = {
        "Sports Centre": 4.5, "Library": 3.2, "Town Hall": 6.0,
        "Training Centre": 5.5, "Student Hostel": 2.8, "Research Centre": 4.0,
    }
    WALK_SPEED = 1.25  # m/s

    trip_rate = TPDM_RATES.get(program_type, 4.5)

    # ═══════════ 1. Site ═══════════
    print(f"  [{time.time()-T0:.0f}s] Loading site...")

    site_gdb = os.path.join(output_gdb, "design_site")
    if not arcpy.Exists(site_gdb):
        arcpy.conversion.FeatureClassToFeatureClass(site_fc, output_gdb, "design_site")

    geoms = []
    with arcpy.da.SearchCursor(site_gdb, ["SHAPE@"]) as cur:
        for row in cur:
            geoms.append(row[0])

    site_union = geoms[0]
    for g in geoms[1:]:
        site_union = site_union.union(g)

    site_shp = shapely_wkt.loads(site_union.WKT)
    center = site_shp.centroid
    buf200 = site_shp.buffer(200)
    buf600 = site_shp.buffer(clip_buffer)

    site_area = site_shp.area
    gfa = site_area * 0.60 * 3  # 60% site coverage × 3 floors
    peak_trips = trip_rate * (gfa / 100)

    print(f"    Area: {site_area/10000:.2f} ha, GFA: {gfa:,.0f} m2, Trips: {peak_trips:.0f}/hr")

    # ═══════════ 2. Road network ═══════════
    print(f"  [{time.time()-T0:.0f}s] Preparing road network...")

    buf_fc = os.path.join(output_gdb, f"site_buf{clip_buffer}")
    if arcpy.Exists(buf_fc):
        arcpy.management.Delete(buf_fc)
    arcpy.management.CreateFeatureclass(output_gdb, f"site_buf{clip_buffer}",
        "POLYGON", spatial_reference=site_gdb)
    with arcpy.da.InsertCursor(buf_fc, ["SHAPE@"]) as cur:
        cur.insertRow([arcpy.FromWKT(buf600.wkt)])

    roads_clip = os.path.join(output_gdb, "roads_clip")
    if arcpy.Exists(roads_clip):
        arcpy.management.Delete(roads_clip)
    arcpy.analysis.Clip(roads_fc, buf_fc, roads_clip)

    # Resolve road attributes (explicit config → auto-detect)
    road_flds = [f.name for f in arcpy.ListFields(roads_clip)]
    try:
        length_fld = resolve_field(roads_clip, road_length_field, ["shape_leng", "length", "road_len", "segment_len"])
    except ValueError:
        length_fld = None
    try:
        time_fld = resolve_field(roads_clip, road_travel_time_field, ["cost_sec", "travel", "travel_time", "time", "tt_sec"])
    except ValueError:
        time_fld = None

    cursor_flds = ["SHAPE@"]
    if length_fld: cursor_flds.append(length_fld)
    if time_fld: cursor_flds.append(time_fld)

    edges = []
    with arcpy.da.SearchCursor(roads_clip, cursor_flds) as cur:
        for row in cur:
            g = shapely_wkt.loads(row[0].WKT)
            length = row[1] if len(row) > 1 and row[1] else 50
            tt = row[2] if len(row) > 2 and row[2] and row[2] > 0 else length / WALK_SPEED

            lines = g.geoms if g.geom_type == "MultiLineString" else [g]
            for line in lines:
                coords = list(line.coords)
                if len(coords) >= 2:
                    edges.append({"coords": coords, "length": length, "travel_time": tt})
    print(f"    Edges: {len(edges)}")

    # ═══════════ 3. Build graph ═══════════
    print(f"  [{time.time()-T0:.0f}s] Building graph...")

    G = nx.Graph()
    for e in edges:
        for i in range(len(e["coords"]) - 1):
            G.add_edge(e["coords"][i], e["coords"][i+1],
                       travel_time=e["travel_time"], length=e["length"])
    print(f"    Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")

    # Node lookup tree
    node_list = list(G.nodes())
    node_arr = np.array(node_list)
    tree = cKDTree(node_arr)

    def snap(x, y):
        _, i = tree.query([x, y])
        return node_list[i]

    site_node = snap(center.x, center.y)
    print(f"    Site node: {site_node}")

    # ═══════════ 4. Population origins ═══════════
    print(f"  [{time.time()-T0:.0f}s] Processing population origins...")

    blocks = []
    with arcpy.da.SearchCursor(pop_fc, ["SHAPE@", pop_field, "ssbg", "ssbg_eng"]) as cur:
        for row in cur:
            avg_pop = float(row[1] or 0)
            if avg_pop <= 0:
                continue
            g = shapely_wkt.loads(row[0].WKT)
            if not g.intersects(buf600):
                continue
            c = g.centroid
            blocks.append({
                "centroid": c, "avg_pop": avg_pop,
                "ssbg": row[2], "ssbg_eng": row[3],
            })

    total_pop = sum(b["avg_pop"] for b in blocks)
    for b in blocks:
        b["trip_share"] = b["avg_pop"] / max(total_pop, 1)
        b["trips"] = b["trip_share"] * peak_trips
        b["origin_node"] = snap(b["centroid"].x, b["centroid"].y)

    print(f"    Blocks: {len(blocks)}, Pop: {total_pop:,.0f}, Trip check: {sum(b['trips'] for b in blocks):.1f}")

    # ═══════════ 5. Network assignment ═══════════
    print(f"  [{time.time()-T0:.0f}s] Running shortest-path assignment...")

    nx.set_edge_attributes(G, 0.0, "load")
    assigned = skipped = 0

    for b in blocks:
        if b["trips"] < 0.05:
            continue
        try:
            path = nx.shortest_path(G, b["origin_node"], site_node, weight="travel_time")
            for u, v in zip(path[:-1], path[1:]):
                if G.has_edge(u, v):
                    G[u][v]["load"] = G[u][v].get("load", 0) + b["trips"]
            assigned += 1
        except nx.NetworkXNoPath:
            skipped += 1
    print(f"    Assigned: {assigned}, Skipped: {skipped}")

    # ═══════════ 6. Build loaded edge layer ═══════════
    print(f"  [{time.time()-T0:.0f}s] Building loaded edge layer...")

    link_fc = os.path.join(output_gdb, "link_loads_tmp")
    if arcpy.Exists(link_fc):
        arcpy.management.Delete(link_fc)
    arcpy.management.CreateFeatureclass(output_gdb, "link_loads_tmp",
        "POLYLINE", spatial_reference=site_gdb)
    for fn in ["load","length_m","tt_sec"]:
        arcpy.management.AddField(link_fc, fn, "DOUBLE")

    with arcpy.da.InsertCursor(link_fc, ["SHAPE@","load","length_m","tt_sec"]) as cur:
        for u, v, data in G.edges(data=True):
            load = data.get("load", 0)
            if load == 0:
                continue
            cur.insertRow([
                arcpy.FromWKT(LineString([u, v]).wkt),
                round(load, 2),
                round(data.get("length", 0), 1),
                round(data.get("travel_time", 0), 1),
            ])

    # Clip to 200m buffer
    buf200_fc = os.path.join(output_gdb, "site_buf200")
    if arcpy.Exists(buf200_fc):
        arcpy.management.Delete(buf200_fc)
    arcpy.management.CreateFeatureclass(output_gdb, "site_buf200",
        "POLYGON", spatial_reference=site_gdb)
    with arcpy.da.InsertCursor(buf200_fc, ["SHAPE@"]) as cur:
        cur.insertRow([arcpy.FromWKT(buf200.wkt)])

    link_clip = os.path.join(output_gdb, "link_loads_200m")
    if arcpy.Exists(link_clip):
        arcpy.management.Delete(link_clip)
    arcpy.analysis.Clip(link_fc, buf200_fc, link_clip)
    print(f"    Loaded edges (200m): {int(arcpy.management.GetCount(link_clip).getOutput(0))}")

    # ═══════════ 7. LOS classification ═══════════
    print(f"  [{time.time()-T0:.0f}s] Computing LOS...")

    LOS_C = 23 / 60; LOS_D = 33 / 60; LOS_E = 49 / 60
    for fn in ["flow_pmpm","LOS","load_norm"]:
        arcpy.management.AddField(link_clip, fn, "DOUBLE" if fn != "LOS" else None)
        if fn == "LOS":
            arcpy.management.DeleteField(link_clip, "LOS")
            arcpy.management.AddField(link_clip, "LOS", "TEXT", field_length=4)

    arcpy.management.CalculateField(link_clip, "flow_pmpm",
        f"!load! / 60 / {walkway_width}", "PYTHON3")

    max_load = 1
    with arcpy.da.SearchCursor(link_clip, ["load"]) as cur:
        for row in cur:
            if row[0] and row[0] > max_load:
                max_load = row[0]

    los_code = f'''c={LOS_C};d={LOS_D};e={LOS_E}
def los(v):
    if v >= e: return "E"
    if v >= d: return "D"
    if v >= c: return "C"
    return "B"'''
    arcpy.management.CalculateField(link_clip, "LOS", "los(!flow_pmpm!)", "PYTHON3", los_code)
    arcpy.management.CalculateField(link_clip, "load_norm", f"!load! / {max_load} * 100", "PYTHON3")

    # ═══════════ 8. Gap detection ═══════════
    print(f"  [{time.time()-T0:.0f}s] Detecting gap zones...")

    gaps_fc = os.path.join(output_gdb, "gap_zones")
    if arcpy.Exists(gaps_fc):
        arcpy.management.Delete(gaps_fc)
    arcpy.management.CreateFeatureclass(output_gdb, "gap_zones",
        "POLYLINE", spatial_reference=site_gdb)
    for fn in ["ssbg_eng","pop","trips_ph","straight","network_m","detour_x","priority"]:
        arcpy.management.AddField(gaps_fc, fn, "DOUBLE" if fn != "ssbg_eng" and fn != "priority" else "TEXT")
        if fn == "ssbg_eng":
            for f in arcpy.ListFields(gaps_fc):
                if f.name == "ssbg_eng" and f.type != "String":
                    arcpy.management.DeleteField(gaps_fc, "ssbg_eng")
                    arcpy.management.AddField(gaps_fc, "ssbg_eng", "TEXT", field_length=100)

    with arcpy.da.InsertCursor(gaps_fc, ["SHAPE@","ssbg_eng","pop","trips_ph",
                                           "straight","network_m","detour_x","priority"]) as cur:
        for b in blocks:
            if b["trips"] < 1.0:
                continue
            straight = b["centroid"].distance(center)
            try:
                path_len = nx.shortest_path_length(G, b["origin_node"], site_node, weight="length")
                ratio = path_len / max(straight, 1)
                if ratio > gap_threshold:
                    priority = "HIGH" if b["trips"] >= 3 else "MEDIUM"
                    cur.insertRow([
                        arcpy.FromWKT(LineString([(b["centroid"].x, b["centroid"].y),
                                                   (center.x, center.y)]).wkt),
                        str(b.get("ssbg_eng",""))[:100],
                        int(b["avg_pop"]),
                        round(b["trips"], 1),
                        round(straight),
                        round(path_len),
                        round(ratio, 2),
                        priority,
                    ])
            except nx.NetworkXNoPath:
                cur.insertRow([
                    arcpy.FromWKT(LineString([(b["centroid"].x, b["centroid"].y),
                                               (center.x, center.y)]).wkt),
                    str(b.get("ssbg_eng",""))[:100],
                    int(b["avg_pop"]),
                    round(b["trips"], 1),
                    round(straight),
                    99999, 99.0, "CRITICAL",
                ])

    print(f"    Gap zones: {int(arcpy.management.GetCount(gaps_fc).getOutput(0))}")
    print(f"  DONE [{time.time()-T0:.0f}s]")
    return link_clip, gaps_fc


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--config", help="JSON config")
    p.add_argument("--site-fc")
    p.add_argument("--roads-fc")
    p.add_argument("--pop-fc")
    p.add_argument("--output-gdb")
    p.add_argument("--pop-field", default="Averag_pop")
    p.add_argument("--road-length-field", default=None)
    p.add_argument("--road-time-field", default=None)
    p.add_argument("--program", default="Sports Centre")
    p.add_argument("--width", type=float, default=3.0)
    p.add_argument("--buffer", type=float, default=600)
    p.add_argument("--gap", type=float, default=1.4)
    args = p.parse_args()

    if args.config:
        with open(args.config,'r',encoding='utf-8') as f:
            cfg = json.load(f)
        fm = cfg.get("field_mapping", {})
        net_cfg = cfg.get("network", {})
        args.site_fc = net_cfg.get("site_fc", args.site_fc)
        args.roads_fc = net_cfg.get("roads_fc", args.roads_fc)
        args.pop_fc = net_cfg.get("pop_fc", args.pop_fc)
        args.output_gdb = cfg.get("output_gdb", args.output_gdb)
        args.pop_field = net_cfg.get("pop_field") or fm.get("population_count", args.pop_field)
        args.road_length_field = net_cfg.get("road_length_field") or fm.get("road_length")
        args.road_time_field = net_cfg.get("road_travel_time_field") or fm.get("road_travel_time")
        args.program = net_cfg.get("program_type", args.program)
        args.width = net_cfg.get("walkway_width", args.width)
        args.buffer = net_cfg.get("clip_buffer", args.buffer)
        args.gap = net_cfg.get("gap_threshold", args.gap)

    network_flow_assignment(
        args.site_fc, args.roads_fc, args.pop_fc,
        args.output_gdb,
        pop_field=args.pop_field,
        road_length_field=args.road_length_field,
        road_travel_time_field=args.road_time_field,
        program_type=args.program,
        walkway_width=args.width,
        clip_buffer=args.buffer,
        gap_threshold=args.gap,
    )
