from pathlib import Path
import json
import joblib
import pandas as pd
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from app.feature_builder import FEATURE_COLUMNS

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed" / "training_features.parquet"
MODEL = ROOT / "artifacts" / "model.joblib"

def main():
    if not DATA.exists() or not MODEL.exists():
        raise FileNotFoundError("Run prepare_training_data.py and train_models.py first.")
    data = pd.read_parquet(DATA)
    test = data[pd.to_datetime(data.source_datetime) > pd.Timestamp("2016-08-31 23:00:00")].copy()
    model = joblib.load(MODEL)
    prediction = model.predict(test[FEATURE_COLUMNS])
    test["prediction"] = prediction
    test["baseline"] = test["pm25_lag_1"]
    rows = []
    for station, group in test.groupby("station"):
        rows.append({
            "station": station,
            "model_mae": float(mean_absolute_error(group.pm25_target, group.prediction)),
            "model_rmse": float(mean_squared_error(group.pm25_target, group.prediction) ** 0.5),
            "baseline_mae": float(mean_absolute_error(group.pm25_target, group.baseline)),
            "baseline_rmse": float(mean_squared_error(group.pm25_target, group.baseline) ** 0.5),
            "r2": float(r2_score(group.pm25_target, group.prediction)),
        })
    output = ROOT / "artifacts" / "metrics_by_station.json"
    output.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(pd.DataFrame(rows).to_string(index=False))
    print("Saved:", output)

if __name__ == "__main__":
    main()
