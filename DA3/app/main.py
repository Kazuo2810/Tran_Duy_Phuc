import asyncio
from contextlib import asynccontextmanager
from datetime import datetime,timezone
from fastapi import FastAPI,HTTPException,Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .config import *
from .model_service import ModelService
from .state import RealtimeState
from .consumer import consume
@asynccontextmanager
async def lifespan(app):
 try:app.state.model=ModelService(MODEL_PATH,FEATURE_COLUMNS_PATH,METRICS_PATH);app.state.model_error=None
 except Exception as e:app.state.model=None;app.state.model_error=str(e)
 app.state.state=RealtimeState(BUFFER_HOURS);app.state.task=asyncio.create_task(consume(app.state.state,app.state.model,FORECAST_HORIZON))
 yield
 app.state.task.cancel()
 try:await app.state.task
 except asyncio.CancelledError:pass
app=FastAPI(title="DA3 Air Quality Forecast API",version="1.0.0",lifespan=lifespan)
app.mount("/static",StaticFiles(directory="dashboard/static"),name="static");templates=Jinja2Templates(directory="dashboard/templates")
@app.get("/",response_class=HTMLResponse)
async def dashboard(request:Request):return templates.TemplateResponse("index.html",{"request":request})
@app.get("/health")
def health():return {"status":"ok","model_loaded":app.state.model is not None,"model_error":app.state.model_error,**app.state.state.status()}
@app.get("/api/v1/model")
def model_info():
 m=app.state.model
 return {"loaded":m is not None,"model_version":MODEL_VERSION,"error":app.state.model_error,"feature_count":len(m.feature_columns) if m else 0,"metrics":m.metrics if m else {}}
@app.get("/api/v1/status")
def status():return app.state.state.status()
@app.get("/api/v1/observations/latest")
def observations():return {"generated_at":datetime.now(timezone.utc).isoformat(),"observations":[dict(v[-1]) for v in app.state.state.buffers.values() if v]}
@app.get("/api/v1/forecasts/latest")
def latest():return {"generated_at":datetime.now(timezone.utc).isoformat(),"count":len(app.state.state.forecasts),"forecasts":list(app.state.state.forecasts.values())}
@app.get("/api/v1/forecasts/{station}")
def station(station:str):
 if station not in app.state.state.forecasts:raise HTTPException(404,"Chưa có dự báo cho trạm này; hệ thống có thể đang warming_up.")
 return app.state.state.forecasts[station]
