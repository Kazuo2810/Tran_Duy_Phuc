from collections import defaultdict,deque
from datetime import datetime,timezone
import pandas as pd
from .feature_builder import normalize,build_latest
class RealtimeState:
 def __init__(self,size=48):
  self.buffers=defaultdict(lambda:deque(maxlen=size));self.forecasts={};self.session_id=None;self.last_sequence=None;self.consumer_connected=False;self.last_event_at=None;self.last_error=None
 def append(self,event):
  sid=event.get("session_id")
  if sid and sid!=self.session_id:self.buffers.clear();self.forecasts.clear();self.last_sequence=None;self.session_id=sid
  seq=event.get("sequence")
  if seq is not None and self.last_sequence is not None and seq<=self.last_sequence:return False
  ts=event.get("source_datetime") or event.get("timestamp");obs=event.get("observations") or event.get("data") or []
  if isinstance(obs,dict):obs=obs.get("observations",[])
  for item in obs:
   row=normalize(item,ts)
   if row.get("source_datetime") is not None:self.buffers[str(row.get("station","unknown"))].append(row)
  if seq is not None:self.last_sequence=seq
  self.last_event_at=datetime.now(timezone.utc).isoformat();return True
 def predict(self,model,horizon):
  if model is None:return
  for station,rows in self.buffers.items():
   f=build_latest(pd.DataFrame(list(rows)))
   if f is None:continue
   latest=sorted(rows,key=lambda x:x["source_datetime"])[-1];t=pd.Timestamp(latest["source_datetime"])
   self.forecasts[station]={"station":station,"observation_time":t.isoformat(),"forecast_time":(t+pd.Timedelta(hours=horizon)).isoformat(),"observed_pm25":float(latest["pm25"]) if pd.notna(latest.get("pm25")) else None,"predicted_pm25":model.predict([f])[0],"horizon_hours":horizon,"model_version":"rf-ensemble-v1","source_session_id":self.session_id,"source_sequence":self.last_sequence}
 def status(self):
  return {"consumer_connected":self.consumer_connected,"source_session_id":self.session_id,"last_sequence":self.last_sequence,"last_event_at":self.last_event_at,"last_error":self.last_error,"buffer_ready_stations":sum(len(v)>=25 for v in self.buffers.values()),"stations_in_buffer":len(self.buffers),"state":"ready" if self.forecasts else "warming_up"}
