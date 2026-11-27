from pathlib import Path
import pandas as pd
from app.feature_builder import add_features,FEATURE_COLUMNS
ROOT=Path(__file__).resolve().parents[1];RAW=ROOT/"data"/"raw";OUT=ROOT/"data"/"processed"
def main():
 files=list(RAW.rglob("PRSA_Data_*.csv"))
 if not files:raise FileNotFoundError("Run python training/download_dataset.py first.")
 d=pd.concat([pd.read_csv(p) for p in files],ignore_index=True)
 d=d.rename(columns={"PM2.5":"pm25","PM10":"pm10","SO2":"so2","NO2":"no2","CO":"co","O3":"o3","TEMP":"temperature","PRES":"pressure","DEWP":"dew_point","RAIN":"rain","WSPM":"wind_speed"})
 d["source_datetime"]=pd.to_datetime(d[["year","month","day","hour"]]);d=d.sort_values(["station","source_datetime"]).drop_duplicates(["station","source_datetime"])
 f=add_features(d,1).dropna(subset=FEATURE_COLUMNS+["pm25_target"]);OUT.mkdir(parents=True,exist_ok=True);f.to_parquet(OUT/"training_features.parquet",index=False)
 print("Prepared rows:",len(f),"stations:",f.station.nunique())
if __name__=="__main__":main()
