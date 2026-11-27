from pathlib import Path
import json,joblib,pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestRegressor,ExtraTreesRegressor,HistGradientBoostingRegressor,VotingRegressor,StackingRegressor
from sklearn.linear_model import Ridge
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score
from app.feature_builder import FEATURE_COLUMNS
ROOT=Path(__file__).resolve().parents[1];DATA=ROOT/"data"/"processed"/"training_features.parquet";OUT=ROOT/"artifacts"
def score(name,m,x,y):
 p=m.predict(x);return {"model":name,"mae":float(mean_absolute_error(y,p)),"rmse":float(mean_squared_error(y,p)**.5),"r2":float(r2_score(y,p))}
def main():
 if not DATA.exists():raise FileNotFoundError("Prepare training data first.")
 d=pd.read_parquet(DATA).sort_values(["source_datetime","station"]);t=pd.to_datetime(d.source_datetime)
 tr=d[t<=pd.Timestamp("2015-12-31 23:00")];va=d[(t>pd.Timestamp("2015-12-31 23:00"))&(t<=pd.Timestamp("2016-08-31 23:00"))];te=d[t>pd.Timestamp("2016-08-31 23:00")]
 if min(len(tr),len(va),len(te))==0:raise ValueError("A chronological split is empty.")
 pre=ColumnTransformer([("station",OneHotEncoder(handle_unknown="ignore",sparse_output=False),["station"]),("numeric","passthrough",[c for c in FEATURE_COLUMNS if c!="station"])])
 rf=RandomForestRegressor(n_estimators=300,max_depth=24,min_samples_leaf=2,max_features=.7,n_jobs=-1,random_state=42)
 et=ExtraTreesRegressor(n_estimators=300,max_depth=24,min_samples_leaf=2,n_jobs=-1,random_state=42)
 hg=HistGradientBoostingRegressor(max_iter=300,learning_rate=.05,max_leaf_nodes=31,random_state=42)
 models={"random_forest":Pipeline([("prep",pre),("model",rf)]),"voting":Pipeline([("prep",pre),("model",VotingRegressor([("rf",rf),("extra",et),("hgb",hg)],weights=[.4,.35,.25],n_jobs=-1))]),"stacking":Pipeline([("prep",pre),("model",StackingRegressor([("rf",rf),("extra",et),("hgb",hg)],final_estimator=Ridge(alpha=1),cv=TimeSeriesSplit(5),n_jobs=-1))])}
 results=[]
 for n,m in models.items():
  print("Training",n);m.fit(tr[FEATURE_COLUMNS],tr.pm25_target);results.append(score(n,m,va[FEATURE_COLUMNS],va.pm25_target))
 results.sort(key=lambda x:x["rmse"]);best=results[0]["model"];final=models[best];tv=pd.concat([tr,va]).sort_values(["source_datetime","station"]);final.fit(tv[FEATURE_COLUMNS],tv.pm25_target);test=score(best,final,te[FEATURE_COLUMNS],te.pm25_target)
 OUT.mkdir(exist_ok=True);joblib.dump(final,OUT/"model.joblib",compress=3);(OUT/"feature_columns.json").write_text(json.dumps(FEATURE_COLUMNS,indent=2));meta={"selected_model":best,"validation":results,"test":test,"target":"PM2.5 at t+1 hour","horizon_hours":1}
 (OUT/"metrics.json").write_text(json.dumps(meta,indent=2));print("Selected",best,"test",test)
if __name__=="__main__":main()
