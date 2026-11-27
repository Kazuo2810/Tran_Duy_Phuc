import asyncio,json,httpx,websockets
from .config import OBSERVATION_HTTP_URL,OBSERVATION_WS_URL,RECONNECT_MIN_SECONDS,RECONNECT_MAX_SECONDS
def events(p):
 if isinstance(p,list):return p
 if isinstance(p,dict):
  if isinstance(p.get("observations"),list):return [p]
  for k in ("events","data","items","history"):
   if isinstance(p.get(k),list):return p[k]
 return []
async def backfill(state,model,horizon):
 async with httpx.AsyncClient(timeout=25) as c:r=await c.get(OBSERVATION_HTTP_URL+"/api/v1/live");r.raise_for_status();payload=r.json()
 for e in events(payload):
  if state.append(e):state.predict(model,horizon)
async def consume(state,model,horizon):
 delay=RECONNECT_MIN_SECONDS
 while True:
  try:
   try:await backfill(state,model,horizon)
   except Exception as e:state.last_error="HTTP backfill: "+str(e)
   url=OBSERVATION_WS_URL.replace("https://","wss://").replace("http://","ws://")
   async with websockets.connect(url+"/ws/v1/live",ping_interval=20,ping_timeout=20,open_timeout=30,max_size=8388608) as ws:
    state.consumer_connected=True;state.last_error=None;delay=RECONNECT_MIN_SECONDS
    async for msg in ws:
     p=json.loads(msg);batch=events(p) or ([p] if isinstance(p,dict) else [])
     for e in batch:
      if state.append(e):state.predict(model,horizon)
  except asyncio.CancelledError:state.consumer_connected=False;raise
  except Exception as e:
   state.consumer_connected=False;state.last_error=str(e);await asyncio.sleep(delay);delay=min(delay*2,RECONNECT_MAX_SECONDS)
