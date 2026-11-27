import numpy as np
import pandas as pd
LAGS=[1,2,3,6,12,24]; WINDOWS=[3,6,12,24]
NUMERIC=["pm25","pm10","so2","no2","co","o3","temperature","pressure","dew_point","rain","wind_speed"]
FEATURE_COLUMNS=["station","hour_sin","hour_cos","dow_sin","dow_cos","month_sin","month_cos",*NUMERIC,*[f"pm25_lag_{x}" for x in LAGS],*[f"pm25_roll_mean_{x}" for x in WINDOWS],*[f"pm25_roll_std_{x}" for x in WINDOWS]
]
ALIASES={"PM2.5":"pm25","PM10":"pm10","SO2":"so2","NO2":"no2","CO":"co","O3":"o3","TEMP":"temperature","PRES":"pressure","DEWP":"dew_point","RAIN":"rain","WSPM":"wind_speed"}
def normalize(row,ts=None):
 d=dict(row)
 for a,b in ALIASES.items():
  if b not in d and a in d:d[b]=d[a]
 if ts is not None:d["source_datetime"]=ts
 if "source_datetime" not in d:
  p=[d.get(k) for k in ("year","month","day","hour")]
  if all(v is not None for v in p):d["source_datetime"]=pd.Timestamp(*map(int,p))
 d.setdefault("station",d.get("station_id","unknown"));return d
def add_features(frame,horizon=1):
 d=frame.copy();d["source_datetime"]=pd.to_datetime(d["source_datetime"]);d=d.sort_values(["station","source_datetime"])
 for c in NUMERIC:
  if c not in d:d[c]=np.nan
 d[NUMERIC]=d.groupby("station")[NUMERIC].ffill();t=d.source_datetime
 for name,val in [("hour_sin",np.sin(2*np.pi*t.dt.hour/24)),("hour_cos",np.cos(2*np.pi*t.dt.hour/24)),("dow_sin",np.sin(2*np.pi*t.dt.dayofweek/7)),("dow_cos",np.cos(2*np.pi*t.dt.dayofweek/7)),("month_sin",np.sin(2*np.pi*(t.dt.month-1)/12)),("month_cos",np.cos(2*np.pi*(t.dt.month-1)/12))]:d[name]=val
 g=d.groupby("station",group_keys=False)
 for lag in LAGS:d[f"pm25_lag_{lag}"]=g.pm25.shift(lag)
 past=g.pm25.shift(1)
 for w in WINDOWS:
  r=past.groupby(d.station).rolling(w)
  d[f"pm25_roll_mean_{w}"]=r.mean().reset_index(level=0,drop=True);d[f"pm25_roll_std_{w}"]=r.std().reset_index(level=0,drop=True)
 d["pm25_target"]=g.pm25.shift(-horizon);return d
def build_latest(frame):
 d=frame.copy();d["source_datetime"]=pd.to_datetime(d.source_datetime);d=d.sort_values("source_datetime").drop_duplicates("source_datetime",keep="last")
 if len(d)<25:return None
 x=d.iloc[-1].copy();t=pd.Timestamp(x.source_datetime);h=d.iloc[:-1]
 x.update({"hour_sin":np.sin(2*np.pi*t.hour/24),"hour_cos":np.cos(2*np.pi*t.hour/24),"dow_sin":np.sin(2*np.pi*t.dayofweek/7),"dow_cos":np.cos(2*np.pi*t.dayofweek/7),"month_sin":np.sin(2*np.pi*(t.month-1)/12),"month_cos":np.cos(2*np.pi*(t.month-1)/12)})
 for c in NUMERIC:
  if c not in x or pd.isna(x[c]):x[c]=h[c].ffill().iloc[-1] if c in h and h[c].notna().any() else 0
 for lag in LAGS:x[f"pm25_lag_{lag}"]=d.pm25.iloc[-1-lag]
 for w in WINDOWS:
  v=d.pm25.iloc[:-1].iloc[-w:];x[f"pm25_roll_mean_{w}"]=v.mean();x[f"pm25_roll_std_{w}"]=v.std()
 return {c:x.get(c) for c in FEATURE_COLUMNS}
