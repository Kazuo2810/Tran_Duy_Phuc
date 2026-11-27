import json,joblib,pandas as pd
class ModelService:
 def __init__(self,model_path,features_path,metrics_path):
  self.model=joblib.load(model_path);self.feature_columns=json.loads(features_path.read_text(encoding="utf-8"));self.metrics=json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
 def predict(self,rows):
  x=pd.DataFrame(rows).reindex(columns=self.feature_columns);return [max(0.,float(v)) for v in self.model.predict(x)]
