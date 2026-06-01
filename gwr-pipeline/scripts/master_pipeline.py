"""
GWR Pipeline — Master Orchestrator
====================================
Runs the full GWR-based facility distribution prediction pipeline.
All parameters are read from a JSON config file (see config_template.json).

Steps:
  1. (Optional) POI time-of-day classification
  2. (Optional) Dasymetric population allocation to buildings
  3. Grid creation + indicator spatial join
  4. GWR model fitting
  5. Future scenario prediction
  6. (Optional) Pedestrian network flow assignment

Usage:
  python master_pipeline.py config.json
  python master_pipeline.py config.json --steps 3,4,5   # selective
"""
import arcpy
import os, sys, json, time

# Add scripts directory to path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from step3_build_grid import build_indicator_grid
from step4_gwr_model import fit_gwr, predict_future


def run_pipeline(config_path, selected_steps=None):
    """Execute the GWR pipeline from a JSON config."""

    with open(config_path, 'r', encoding='utf-8') as f:
        cfg = json.load(f)

    T0 = time.time()

    arcpy.env.overwriteOutput = True
    arcpy.env.workspace = cfg["output_gdb"]

    # Load optional settings
    crs = cfg.get("crs", "EPSG:2326")
    fm = cfg.get("field_mapping", {})  # field name defaults

    all_steps = ["classify", "dasymetric", "grid", "gwr_fit", "gwr_predict", "network"]
    if selected_steps:
        steps = [s.strip() for s in selected_steps.split(",")]
    else:
        steps = cfg.get("steps", all_steps)

    results = {}

    # ── Step 1: POI Classification ──
    if "classify" in steps:
        print(f"\n{'='*60}\nSTEP 1: POI Classification\n{'='*60}")
        from step1_classify_poi import classify_poi_time

        poi_cfg = cfg.get("poi_classification", {})
        if poi_cfg:
            poi_layers = poi_cfg.get("poi_layers", {})
            # Resolve paths relative to config
            base = os.path.dirname(config_path)
            poi_layers = {k: os.path.join(base, v) if not os.path.isabs(v) else v
                          for k, v in poi_layers.items()}

            classify_poi_time(
                poi_layers=poi_layers,
                output_gdb=cfg["output_gdb"],
                midtype_field=poi_cfg.get("midtype_field", "midType"),
                day_set=set(poi_cfg.get("day_set", [])),
                night_set=set(poi_cfg.get("night_set", [])),
                both_set=set(poi_cfg.get("both_set", [])),
            )
            results["poi_fc"] = os.path.join(cfg["output_gdb"], "poi_all_time_classified")

    # ── Step 2: Dasymetric Population ──
    if "dasymetric" in steps:
        print(f"\n{'='*60}\nSTEP 2: Dasymetric Population Allocation\n{'='*60}")
        from step2_pop_allocate import dasymetric_population

        pop_cfg = cfg.get("dasymetric", {})
        if pop_cfg:
            base = os.path.dirname(config_path)
            pop_fc = pop_cfg["pop_fc"]
            bldg_fc = pop_cfg["bldg_fc"]
            if not os.path.isabs(pop_fc):
                pop_fc = os.path.join(base, pop_fc)
            if not os.path.isabs(bldg_fc):
                bldg_fc = os.path.join(base, bldg_fc)

            dasymetric_population(
                pop_fc=pop_fc,
                bldg_fc=bldg_fc,
                output_gdb=cfg["output_gdb"],
                pop_field=pop_cfg.get("pop_field") or fm.get("population_count", "Averag_pop"),
                elev_field=pop_cfg.get("elev_field") or fm.get("building_elevation", "Elevation"),
                fallback_height=pop_cfg.get("fallback_height", 3.0),
            )

    # ── Step 3: Grid + Indicators ──
    if "grid" in steps:
        print(f"\n{'='*60}\nSTEP 3: Grid Creation + Indicator Spatial Join\n{'='*60}")

        grid_cfg = cfg.get("grid", {})
        base = os.path.dirname(config_path)

        site_fc = grid_cfg["site_fc"]
        poi_fc = grid_cfg.get("poi_fc") or results.get("poi_fc")
        pop_fc = grid_cfg["pop_fc"]
        roads_fc = grid_cfg["roads_fc"]

        for k in ["site_fc", "poi_fc", "pop_fc", "roads_fc"]:
            val = grid_cfg.get(k)
            if val and not os.path.isabs(val):
                grid_cfg[k] = os.path.join(base, val)

        if grid_cfg.get("poi_fc") and not os.path.isabs(grid_cfg["poi_fc"]):
            grid_cfg["poi_fc"] = os.path.join(base, grid_cfg["poi_fc"])
        elif not grid_cfg.get("poi_fc"):
            grid_cfg["poi_fc"] = poi_fc

        grid_full, grid_active = build_indicator_grid(
            site_fc=grid_cfg["site_fc"],
            poi_fc=grid_cfg["poi_fc"],
            pop_fc=grid_cfg["pop_fc"],
            roads_fc=grid_cfg["roads_fc"],
            output_gdb=cfg["output_gdb"],
            cell_size=grid_cfg.get("cell_size", 50),
            study_buffer=grid_cfg.get("study_buffer", 1500),
            pop_field=grid_cfg.get("pop_field") or fm.get("population_count", "Averag_pop"),
            road_length_field=grid_cfg.get("road_length_field") or fm.get("road_length", "Shape_Leng"),
            crs=crs,
        )
        results["grid_active"] = grid_active
        results["grid_full"] = grid_full

    # ── Step 4: GWR Fit ──
    if "gwr_fit" in steps:
        print(f"\n{'='*60}\nSTEP 4: GWR Model Fitting\n{'='*60}")

        gwr_cfg = cfg.get("gwr", {})
        grid_active = gwr_cfg.get("grid_active") or results.get("grid_active")

        if not grid_active:
            # Try default path
            grid_active = os.path.join(cfg["output_gdb"], "grid_active_cells")
        if not os.path.isabs(grid_active):
            grid_active = os.path.join(os.path.dirname(config_path), grid_active)

        fit_gwr(
            grid_active_fc=grid_active,
            dependent_var=gwr_cfg.get("dependent", "poi_count"),
            explanatory_vars=gwr_cfg.get("explanatory", ["pop_density", "road_density"]),
            output_gdb=cfg["output_gdb"],
            output_name=gwr_cfg.get("output_name", "gwr_results"),
            neighborhood_type=gwr_cfg.get("neighborhood_type", "NUMBER_OF_NEIGHBORS"),
            selection_method=gwr_cfg.get("selection_method", "GOLDEN_SEARCH"),
            min_neighbors=gwr_cfg.get("min_neighbors", 30),
            num_neighbors=gwr_cfg.get("num_neighbors"),
            scale_data=gwr_cfg.get("scale_data", True),
        )

    # ── Step 5: Future Prediction ──
    if "gwr_predict" in steps:
        print(f"\n{'='*60}\nSTEP 5: Future Scenario Prediction\n{'='*60}")

        pred_cfg = cfg.get("prediction", {})
        grid_active = pred_cfg.get("grid_active") or results.get("grid_active")
        if not grid_active:
            grid_active = os.path.join(cfg["output_gdb"], "grid_active_cells")
        if not os.path.isabs(grid_active):
            grid_active = os.path.join(os.path.dirname(config_path), grid_active)

        prediction_fc = pred_cfg["prediction_fc"]
        if not os.path.isabs(prediction_fc):
            prediction_fc = os.path.join(os.path.dirname(config_path), prediction_fc)

        predict_future(
            grid_active_fc=grid_active,
            dependent_var=pred_cfg.get("dependent", "poi_count"),
            explanatory_vars=pred_cfg.get("explanatory", ["pop_density", "road_density"]),
            output_gdb=cfg["output_gdb"],
            prediction_fc=prediction_fc,
            prediction_output_name=pred_cfg.get("output_name", "gwr_prediction_future"),
            neighborhood_type=pred_cfg.get("neighborhood_type", "NUMBER_OF_NEIGHBORS"),
            num_neighbors=pred_cfg.get("num_neighbors"),
        )

    # ── Step 6: Network Assignment ──
    if "network" in steps:
        print(f"\n{'='*60}\nSTEP 6: Pedestrian Network Flow Assignment\n{'='*60}")

        net_cfg = cfg.get("network", {})
        from step5_net_assign import network_flow_assignment

        base = os.path.dirname(config_path)
        for k in ["site_fc","roads_fc","pop_fc"]:
            if k in net_cfg and not os.path.isabs(net_cfg[k]):
                net_cfg[k] = os.path.join(base, net_cfg[k])

        fm = cfg.get("field_mapping", {})
        network_flow_assignment(
            site_fc=net_cfg["site_fc"],
            roads_fc=net_cfg["roads_fc"],
            pop_fc=net_cfg["pop_fc"],
            output_gdb=cfg["output_gdb"],
            pop_field=net_cfg.get("pop_field") or fm.get("population_count", "Averag_pop"),
            road_length_field=net_cfg.get("road_length_field") or fm.get("road_length"),
            road_travel_time_field=net_cfg.get("road_travel_time_field") or fm.get("road_travel_time"),
            program_type=net_cfg.get("program_type", "Sports Centre"),
            walkway_width=net_cfg.get("walkway_width", 3.0),
            clip_buffer=net_cfg.get("clip_buffer", 600),
            gap_threshold=net_cfg.get("gap_threshold", 1.4),
        )

    elapsed = time.time() - T0
    print(f"\n{'='*60}")
    print(f"PIPELINE COMPLETE [{elapsed:.0f}s]")
    print(f"  Output GDB: {cfg['output_gdb']}")
    if "output_gpkg" in cfg:
        print(f"  Output GPKG: {cfg['output_gpkg']}")
    print(f"{'='*60}")


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="GWR Pipeline Master")
    p.add_argument("config", help="JSON configuration file")
    p.add_argument("--steps", help="Comma-separated steps to run (default: all)")
    args = p.parse_args()
    run_pipeline(args.config, args.steps)
