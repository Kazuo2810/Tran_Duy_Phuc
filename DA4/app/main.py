from __future__ import annotations

from pathlib import Path
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from .recommender import MovieRecommender

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "static"

app = FastAPI(
    title="DA4 - Movie Recommendation System",
    description="Hybrid movie recommendations using MovieLens latest-small.",
    version="1.0.0",
)

app.mount("/static", StaticFiles(directory=STATIC), name="static")
recommender = None


@app.on_event("startup")
def load_model():
    global recommender
    recommender = MovieRecommender()


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health():
    return {
        "status": "ok" if recommender is not None else "model_not_loaded",
        "service": "DA4 Movie Recommendation System",
        "model_loaded": recommender is not None,
    }


@app.get("/api/stats")
def stats():
    return recommender.stats()


@app.get("/api/popular")
def popular(limit: int = Query(12, ge=1, le=50)):
    return {"items": recommender.popular(limit)}


@app.get("/api/search")
def search(q: str = Query(..., min_length=1), limit: int = Query(12, ge=1, le=50)):
    return {"items": recommender.search(q, limit)}


@app.get("/api/recommend/user/{user_id}")
def recommend_user(user_id: int, limit: int = Query(10, ge=1, le=30)):
    try:
        return {"user_id": user_id, "items": recommender.recommend_for_user(user_id, limit)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/recommend/movie/{movie_id}")
def recommend_movie(movie_id: int, limit: int = Query(10, ge=1, le=30)):
    try:
        return {"movie_id": movie_id, "items": recommender.recommend_for_movie(movie_id, limit)}
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
