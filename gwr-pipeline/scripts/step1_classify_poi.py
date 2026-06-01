"""
GWR Pipeline — Step 1: POI Time-of-Day Classification
=======================================================
Reclassifies facility/POI datasets into time-of-day operation classes
based on a configurable category mapping dictionary.

Input:
  - poi_layers: dict[str, str]  — {category_name: path_to_feature_class}
  - day_midtypes: set[str]       — midType values for daytime operation
  - night_midtypes: set[str]     — midType values for nighttime operation
  - both_midtypes: set[str]      — midType values for all-day operation
  - output_gdb: str              — path to output File Geodatabase

Output (in output_gdb):
  - poi_all_time_classified      — merged FC with 'time_class', 'category' fields
  - poi_time_daytime             — daytime-only subset
  - poi_time_nighttime           — nighttime-only subset
  - poi_time_both                — all-day subset

Usage:
  python step1_classify_poi.py --config my_config.py
"""
import arcpy
import os, sys, json, time

from _utils import resolve_field, with_default

# ── Default classification rules (Hong Kong context) ── can be overridden ────
DEFAULT_DAYTIME = {
    "公司","知名企业","公司企业","银行","金融保险服务机构","银行相关",
    "中介机构","邮局","物流速递","家居建材市场","花鸟鱼虫市场",
    "维修站点","摄影冲印店","学校","培训机构","科研机构","传媒机构",
    "文艺团体","会展中心","住宅区",
}
DEFAULT_NIGHTTIME = {"休闲餐饮场所","茶艺馆","冷饮店","休闲场所"}
DEFAULT_BOTH = {
    "中餐厅","外国餐厅","快餐厅","咖啡厅","糕饼店","甜品店","餐饮相关场所",
    "便民商店/便利店","超级市场","商场","专卖店","服装鞋帽皮具店",
    "体育用品店","家电电子卖场","个人用品/化妆品店","文化用品店","购物相关场所",
    "宾馆酒店","旅馆招待所","美容美发店","洗衣店","自动提款机",
    "电讯营业厅","旅行社","生活服务场所","诊所","综合医院","专科医院",
    "急救中心","医药保健销售店","医疗保健服务场所","图书馆","博物馆",
    "美术馆","展览馆","科教文化场所","科技馆","天文馆","文化宫",
    "运动场馆","体育休闲服务场所","高尔夫相关",
}


def classify_poi_time(poi_layers, output_gdb, midtype_field="midType",
                       day_set=None, night_set=None, both_set=None,
                       arcpy_env=None):
    """
    Classify POI feature classes by time-of-day operation.

    Parameters
    ----------
    poi_layers : dict
        {category_name: feature_class_path}
    output_gdb : str
        Path to output File Geodatabase
    midtype_field : str
        Field containing POI sub-type (default 'midType')
    day_set, night_set, both_set : set or None
        Classification word sets. None = use defaults.
    arcpy_env : dict or None
        Extra arcpy environment settings
    """
    T0 = time.time()
    day_set   = day_set or DEFAULT_DAYTIME
    night_set = night_set or DEFAULT_NIGHTTIME
    both_set  = both_set or DEFAULT_BOTH

    if arcpy_env:
        for k, v in arcpy_env.items():
            setattr(arcpy.env, k, v)
    arcpy.env.workspace = output_gdb
    arcpy.env.overwriteOutput = True

    day_str   = repr(list(day_set))
    night_str = repr(list(night_set))
    both_str  = repr(list(both_set))

    CODE = f'''
daytime = {day_str}
nighttime = {night_str}
both = {both_str}
labels = {{"daytime":"1-Daytime (8am-6pm)","nighttime":"2-Nighttime (6pm-midnight)","both":"3-Both/All-day"}}

def classify_time(mt):
    if mt is None:
        return "both"
    s = str(mt).strip()
    if s in daytime: return "daytime"
    elif s in nighttime: return "nighttime"
    elif s in both: return "both"
    return "both"

def get_label(tc):
    return labels.get(tc, tc)
'''

    FIELDS = [
        ("time_class", "TEXT", 20),
        ("time_label", "TEXT", 60),
        ("category",   "TEXT", 20),
    ]

    classified_fcs = []

    for cat_name, fc_path in poi_layers.items():
        src_fc = os.path.join(output_gdb, f"poi_{cat_name}_raw")
        if arcpy.Exists(src_fc):
            arcpy.management.Delete(src_fc)

        # Copy into GDB
        arcpy.conversion.FeatureClassToFeatureClass(fc_path, output_gdb, f"poi_{cat_name}_raw")
        cnt = int(arcpy.management.GetCount(src_fc).getOutput(0))
        print(f"  [{time.time()-T0:.0f}s] {cat_name}: {cnt} features")

        existing = {f.name for f in arcpy.ListFields(src_fc)}
        for fn, ft, fl in FIELDS:
            if fn not in existing:
                arcpy.management.AddField(src_fc, fn, ft, field_length=fl)

        arcpy.management.CalculateField(src_fc, "category", f"'{cat_name}'", "PYTHON3")

        # Resolve midType field name (explicit config or auto-detect)
        try:
            mt_fld = resolve_field(src_fc, midtype_field, ["midtype", "mid_type", "midtyp"])
        except ValueError:
            mt_fld = None

        if mt_fld:
            arcpy.management.CalculateField(src_fc, "time_class",
                f"classify_time(!{mt_fld}!)", "PYTHON3", CODE)
        else:
            existing = [f.name for f in arcpy.ListFields(src_fc)]
            print(f"    WARNING: midType field not found; defaulting to 'both'."
                  f"  Available fields: {existing[:15]}")
            arcpy.management.CalculateField(src_fc, "time_class", "'both'", "PYTHON3")

        arcpy.management.CalculateField(src_fc, "time_label",
            "get_label(!time_class!)", "PYTHON3", CODE)

        # Count distribution
        tc_cnt = {"daytime":0,"nighttime":0,"both":0}
        with arcpy.da.SearchCursor(src_fc, ["time_class"]) as cur:
            for row in cur:
                tc_cnt[row[0] if row[0] in tc_cnt else "both"] += 1
        for k, v in tc_cnt.items():
            print(f"    {k}: {v} ({v/cnt*100:.1f}%)")

        classified_fcs.append(src_fc)

    # Merge
    merged = os.path.join(output_gdb, "poi_all_time_classified")
    if arcpy.Exists(merged):
        arcpy.management.Delete(merged)
    arcpy.management.Merge(classified_fcs, merged)
    total = int(arcpy.management.GetCount(merged).getOutput(0))
    print(f"  Merged: {total} total POIs")

    # Split
    for cls in ["daytime","nighttime","both"]:
        out = os.path.join(output_gdb, f"poi_time_{cls}")
        if arcpy.Exists(out):
            arcpy.management.Delete(out)
        arcpy.analysis.Select(merged, out, f"time_class = '{cls}'")
        print(f"  poi_time_{cls}: {int(arcpy.management.GetCount(out).getOutput(0))}")

    print(f"  DONE [{time.time()-T0:.0f}s]")
    return merged


if __name__ == "__main__":
    # Example usage (override via --config or edit directly)
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--config", help="JSON config file")
    p.add_argument("--poi-dir", help="Directory with POI GPKG files")
    p.add_argument("--output-gdb", help="Output GDB path")
    p.add_argument("--day-set", nargs="*", help="Daytime midTypes")
    p.add_argument("--night-set", nargs="*", help="Nighttime midTypes")
    p.add_argument("--both-set", nargs="*", help="Both midTypes")
    args = p.parse_args()

    if args.config:
        with open(args.config, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
        args.poi_dir    = cfg.get('poi_dir', args.poi_dir)
        args.output_gdb = cfg.get('output_gdb', args.output_gdb)
        day_set   = set(cfg.get('day_set', []))
        night_set = set(cfg.get('night_set', []))
        both_set  = set(cfg.get('both_set', []))
    else:
        day_set   = set(args.day_set) if args.day_set else DEFAULT_DAYTIME
        night_set = set(args.night_set) if args.night_set else DEFAULT_NIGHTTIME
        both_set  = set(args.both_set) if args.both_set else DEFAULT_BOTH

    if not args.poi_dir or not args.output_gdb:
        p.error("--poi-dir and --output-gdb required (or --config)")

    from glob import glob
    layers = {}
    for gpkg in glob(os.path.join(args.poi_dir, "*.gpkg")):
        label = os.path.splitext(os.path.basename(gpkg))[0]
        layers[label] = gpkg

    classify_poi_time(layers, args.output_gdb,
                       day_set=day_set, night_set=night_set, both_set=both_set)
