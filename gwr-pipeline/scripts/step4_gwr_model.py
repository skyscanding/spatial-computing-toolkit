"""
GWR Pipeline — Step 4: GWR Model Fitting + Future Scenario Prediction
=======================================================================
Fits a Geographically Weighted Regression model using arcpy.stats.GWR
to estimate spatially-varying relationships between POI/facility density
and built-environment indicators. Then applies the model to a future
scenario (population projections, infrastructure changes) to predict
future facility distribution.

Input:
  - grid_active_fc: str     — grid cells with POI > 0 (from step 3)
  - dependent_var: str       — field name for dependent variable (e.g. 'poi_count')
  - explanatory_vars: list[str] — field names for independent variables
  - output_gdb: str          — output GDB
  - prediction_fc: str       — optional future scenario grid
  - neighborhood_type: str   — 'NUMBER_OF_NEIGHBORS' or 'DISTANCE_BAND'
  - selection_method: str    — 'GOLDEN_SEARCH', 'MANUAL_INTERVALS', 'USER_DEFINED'
  - num_neighbors: int       — fixed neighbor count (if USER_DEFINED)
  - scale_data: bool          — whether to standardize variables

Output (in output_gdb):
  - gwr_results               — fitted GWR model output
  - gwr_prediction_future     — predicted values for future scenario

Usage:
  python step4_gwr_model.py --config my_config.py
"""
import arcpy
import os, sys, json, time
import numpy as np


def fit_gwr(grid_active_fc, dependent_var, explanatory_vars,
             output_gdb, output_name="gwr_results",
             neighborhood_type="NUMBER_OF_NEIGHBORS",
             selection_method="GOLDEN_SEARCH",
             min_neighbors=30,
             num_neighbors=None,
             bandwidth=None,
             scale_data=True,
             arcpy_env=None):
    """
    Fit a GWR model.

    Returns the path to the output feature class.
    """
    T0 = time.time()
    if arcpy_env:
        for k, v in arcpy_env.items():
            setattr(arcpy.env, k, v)
    arcpy.env.workspace = output_gdb
    arcpy.env.overwriteOutput = True

    print(f"  [{time.time()-T0:.0f}s] Preparing GWR...")
    print(f"    Dependent: {dependent_var}")
    print(f"    Explanatory: {explanatory_vars}")
    print(f"    Active features: {int(arcpy.management.GetCount(grid_active_fc).getOutput(0))}")

    # Validate explanatory variables have sufficient variation
    for var in explanatory_vars:
        vals = [r[0] for r in arcpy.da.SearchCursor(grid_active_fc, [var]) if r[0] is not None]
        if not vals:
            print(f"    WARNING: '{var}' has no data")
        elif np.std(vals) < 0.0001:
            print(f"    WARNING: '{var}' has near-zero variance")

    # Null-value cleanup
    for var in [dependent_var] + explanatory_vars:
        with arcpy.da.UpdateCursor(grid_active_fc, [var]) as cur:
            for row in cur:
                if row[0] is None:
                    row[0] = 0
                    cur.updateRow(row)

    out_fc = os.path.join(output_gdb, output_name)
    if arcpy.Exists(out_fc):
        arcpy.management.Delete(out_fc)

    scale_opt = "SCALE_DATA" if scale_data else "NO_SCALE_DATA"

    print(f"  [{time.time()-T0:.0f}s] Fitting GWR (this may take a while)...")

    if selection_method == "USER_DEFINED":
        arcpy.stats.GWR(
            in_features=grid_active_fc,
            dependent_variable=dependent_var,
            model_type="CONTINUOUS",
            explanatory_variables=explanatory_vars,
            output_features=out_fc,
            neighborhood_type=neighborhood_type,
            neighborhood_selection_method="USER_DEFINED",
            number_of_neighbors=num_neighbors or 100,
            local_weighting_scheme="BISQUARE",
            scale=scale_opt,
        )
    elif selection_method == "GOLDEN_SEARCH":
        arcpy.stats.GWR(
            in_features=grid_active_fc,
            dependent_variable=dependent_var,
            model_type="CONTINUOUS",
            explanatory_variables=explanatory_vars,
            output_features=out_fc,
            neighborhood_type=neighborhood_type,
            neighborhood_selection_method="GOLDEN_SEARCH",
            minimum_number_of_neighbors=min_neighbors,
            local_weighting_scheme="BISQUARE",
            scale=scale_opt,
        )
    elif selection_method == "MANUAL_INTERVALS":
        arcpy.stats.GWR(
            in_features=grid_active_fc,
            dependent_variable=dependent_var,
            model_type="CONTINUOUS",
            explanatory_variables=explanatory_vars,
            output_features=out_fc,
            neighborhood_type=neighborhood_type,
            neighborhood_selection_method="MANUAL_INTERVALS",
            minimum_number_of_neighbors=min_neighbors,
            number_of_neighbors_increment=20,
            number_of_increments=10,
            local_weighting_scheme="BISQUARE",
            scale=scale_opt,
        )
    else:
        # Basic GWR
        arcpy.stats.GWR(
            in_features=grid_active_fc,
            dependent_variable=dependent_var,
            model_type="CONTINUOUS",
            explanatory_variables=explanatory_vars,
            output_features=out_fc,
            neighborhood_type=neighborhood_type,
            neighborhood_selection_method="GOLDEN_SEARCH",
            minimum_number_of_neighbors=30,
            scale=scale_opt,
        )

    # Print diagnostics
    for f in arcpy.ListFields(out_fc):
        fn = f.name.upper()
        if any(k in fn for k in ["R2","AIC","RESIDUAL","COND"]):
            vals = [r[0] for r in arcpy.da.SearchCursor(out_fc, [f.name]) if r[0] is not None]
            if vals:
                print(f"    {f.name}: mean={np.mean(vals):.4f}")

    print(f"  DONE [{time.time()-T0:.0f}s]")
    return out_fc


def predict_future(grid_active_fc, dependent_var, explanatory_vars,
                    output_gdb, prediction_fc,
                    gwr_output_name="gwr_results",
                    prediction_output_name="gwr_prediction_future",
                    neighborhood_type="NUMBER_OF_NEIGHBORS",
                    num_neighbors=None,
                    arcpy_env=None):
    """
    Use a fitted GWR model to predict on a future scenario grid.

    The prediction_fc must contain fields with the SAME names as the
    explanatory variables used in the GWR training data.

    Returns the path to the prediction output feature class.
    """
    T0 = time.time()
    if arcpy_env:
        for k, v in arcpy_env.items():
            setattr(arcpy.env, k, v)
    arcpy.env.workspace = output_gdb
    arcpy.env.overwriteOutput = True

    print(f"  [{time.time()-T0:.0f}s] Predicting on future scenario...")
    print(f"    Prediction locations: {int(arcpy.management.GetCount(prediction_fc).getOutput(0))} features")

    pred_out = os.path.join(output_gdb, prediction_output_name)
    if arcpy.Exists(pred_out):
        arcpy.management.Delete(pred_out)

    # Ensure prediction FC has all required explanatory variable fields
    pred_fields = {f.name for f in arcpy.ListFields(prediction_fc)}
    for var in explanatory_vars:
        if var not in pred_fields:
            arcpy.management.AddField(prediction_fc, var, "DOUBLE")

    # Null cleanup on prediction FC
    for var in explanatory_vars:
        with arcpy.da.UpdateCursor(prediction_fc, [var]) as cur:
            for row in cur:
                if row[0] is None:
                    row[0] = 0
                    cur.updateRow(row)

    # Fit + predict in one call
    # (arcpy.stats.GWR can take prediction_locations to do both)
    out_train = os.path.join(output_gdb, gwr_output_name)
    if arcpy.Exists(out_train):
        arcpy.management.Delete(out_train)

    if num_neighbors:
        arcpy.stats.GWR(
            in_features=grid_active_fc,
            dependent_variable=dependent_var,
            model_type="CONTINUOUS",
            explanatory_variables=explanatory_vars,
            output_features=out_train,
            neighborhood_type=neighborhood_type,
            neighborhood_selection_method="USER_DEFINED",
            number_of_neighbors=num_neighbors,
            local_weighting_scheme="BISQUARE",
            scale="SCALE_DATA",
            prediction_locations=prediction_fc,
            explanatory_variables_to_match=explanatory_vars,
            output_predicted_features=pred_out,
        )
    else:
        arcpy.stats.GWR(
            in_features=grid_active_fc,
            dependent_variable=dependent_var,
            model_type="CONTINUOUS",
            explanatory_variables=explanatory_vars,
            output_features=out_train,
            neighborhood_type=neighborhood_type,
            neighborhood_selection_method="GOLDEN_SEARCH",
            minimum_number_of_neighbors=30,
            local_weighting_scheme="BISQUARE",
            scale="SCALE_DATA",
            prediction_locations=prediction_fc,
            explanatory_variables_to_match=explanatory_vars,
            output_predicted_features=pred_out,
        )

    pred_cnt = int(arcpy.management.GetCount(pred_out).getOutput(0))
    print(f"    Prediction output: {pred_cnt} features")
    print(f"  DONE [{time.time()-T0:.0f}s]")
    return pred_out


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--config", help="JSON config")
    p.add_argument("--grid-active", help="Active grid FC (training data)")
    p.add_argument("--dependent", default="poi_count")
    p.add_argument("--explanatory", nargs="*", default=["pop_density","road_density"])
    p.add_argument("--output-gdb", help="Output GDB")
    p.add_argument("--prediction-fc", help="Future scenario grid (optional)")
    p.add_argument("--neighborhood", default="NUMBER_OF_NEIGHBORS")
    p.add_argument("--selection", default="GOLDEN_SEARCH")
    p.add_argument("--num-neighbors", type=int, default=None)
    p.add_argument("--scale/--no-scale", default=True)
    args = p.parse_args()

    if args.config:
        with open(args.config,'r',encoding='utf-8') as f:
            cfg = json.load(f)
        for k in ['grid_active','dependent','explanatory','output_gdb',
                   'prediction_fc','neighborhood','selection','num_neighbors']:
            if k in cfg:
                setattr(args, k, cfg[k])

    fit_gwr(args.grid_active, args.dependent, args.explanatory, args.output_gdb,
             neighborhood_type=args.neighborhood,
             selection_method=args.selection,
             num_neighbors=args.num_neighbors,
             scale_data=args.scale)

    if args.prediction_fc and arcpy.Exists(args.prediction_fc):
        predict_future(args.grid_active, args.dependent, args.explanatory,
                        args.output_gdb, args.prediction_fc,
                        neighborhood_type=args.neighborhood,
                        num_neighbors=args.num_neighbors)
