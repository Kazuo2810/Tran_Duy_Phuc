import os
from pathlib import Path
from dotenv import load_dotenv
ROOT=Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
def path_env(key,default):
 p=Path(os.getenv(key,default)); return p if p.is_absolute() else ROOT/p
OBSERVATION_HTTP_URL=os.getenv("OBSERVATION_HTTP_URL","https://beijing-observation-simulator.onrender.com").rstrip("/")
OBSERVATION_WS_URL=os.getenv("OBSERVATION_WS_URL","wss://beijing-observation-simulator.onrender.com").rstrip("/")
MODEL_PATH=path_env("MODEL_PATH","artifacts/model.joblib")
FEATURE_COLUMNS_PATH=path_env("FEATURE_COLUMNS_PATH","artifacts/feature_columns.json")
METRICS_PATH=path_env("METRICS_PATH","artifacts/metrics.json")
BUFFER_HOURS=max(25,int(os.getenv("BUFFER_HOURS","48")))
FORECAST_HORIZON=max(1,int(os.getenv("FORECAST_HORIZON","1")))
MODEL_VERSION=os.getenv("MODEL_VERSION","rf-ensemble-v1")
RECONNECT_MIN_SECONDS=float(os.getenv("RECONNECT_MIN_SECONDS","2"))
RECONNECT_MAX_SECONDS=float(os.getenv("RECONNECT_MAX_SECONDS","30"))
