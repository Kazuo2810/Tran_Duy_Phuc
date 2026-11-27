from __future__ import annotations

from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix

ARTIFACT_PATH = Path(__file__).resolve().parents[1] / "artifacts" / "movie_recommender.joblib"


class MovieRecommender:
    def __init__(self, artifact_path: Path = ARTIFACT_PATH):
        if not artifact_path.exists():
            raise FileNotFoundError(
                f"Model artifact not found: {artifact_path}. "
                "Run python -m training.train before starting the API."
            )
        data = joblib.load(artifact_path)
        self.movies: pd.DataFrame = data["movies"]
        self.user_item: csr_matrix = data["user_item"]
        self.item_similarity: csr_matrix = data["item_similarity"]
        self.content_features: csr_matrix = data["content_features"]
        self.movie_to_idx = data["movie_to_idx"]
        self.user_to_idx = data["user_to_idx"]
        self.idx_to_movie = data["idx_to_movie"]
        self.popularity = data["popularity"]
        self.mean_rating = data["mean_rating"]

    def stats(self):
        return {
            "movies": int(len(self.movies)),
            "users": int(len(self.user_to_idx)),
            "ratings": int(self.user_item.nnz),
            "mean_rating": round(float(self.mean_rating), 2),
            "model": "Hybrid: Item-based Collaborative Filtering + TF-IDF Content",
        }

    def search(self, query: str, limit: int = 12):
        query = query.strip().lower()
        if not query:
            return []
        mask = self.movies["title"].str.lower().str.contains(query, regex=False, na=False)
        rows = self.movies.loc[mask].head(limit)
        return [self._movie_payload(row) for _, row in rows.iterrows()]

    def popular(self, limit: int = 12):
        ranked = self.movies.copy()
        ranked["popularity_score"] = self.popularity
        ranked = ranked.sort_values(
            ["popularity_score", "average_rating"], ascending=False
        ).head(limit)
        return [self._movie_payload(row) for _, row in ranked.iterrows()]

    def recommend_for_user(self, user_id: int, limit: int = 10):
        if user_id not in self.user_to_idx:
            raise KeyError(f"Không tìm thấy userId={user_id} trong dữ liệu MovieLens.")

        user_idx = self.user_to_idx[user_id]
        rated = self.user_item.getrow(user_idx)
        cf_scores = np.asarray(rated @ self.item_similarity).ravel()

        if rated.nnz:
            rated_items = rated.indices
            rated_values = rated.data
            liked = rated_items[rated_values >= 4.0]
            if len(liked) == 0:
                liked = rated_items[np.argsort(rated_values)[-min(3, len(rated_values)):]]
            liked_profile = csr_matrix(self.content_features[liked].mean(axis=0))
            content_scores = np.asarray(
                (liked_profile @ self.content_features.T).toarray()
            ).ravel()
        else:
            content_scores = np.zeros(len(self.movies), dtype=float)

        cf_norm = self._normalize(cf_scores)
        content_norm = self._normalize(content_scores)
        popularity_norm = self._normalize(self.popularity)
        hybrid = 0.65 * cf_norm + 0.25 * content_norm + 0.10 * popularity_norm

        if rated.nnz:
            hybrid[rated.indices] = -1

        indices = np.argsort(hybrid)[::-1]
        results = []
        for idx in indices:
            if hybrid[idx] < 0:
                continue
            payload = self._movie_payload(self.movies.iloc[idx])
            payload["recommendation_score"] = round(float(hybrid[idx]), 4)
            results.append(payload)
            if len(results) >= limit:
                break
        return results

    def recommend_for_movie(self, movie_id: int, limit: int = 10):
        if movie_id not in self.movie_to_idx:
            raise KeyError(f"Không tìm thấy movieId={movie_id}.")

        idx = self.movie_to_idx[movie_id]
        cf = self.item_similarity.getrow(idx).toarray().ravel()
        content = (self.content_features[idx] @ self.content_features.T).toarray().ravel()
        score = 0.55 * self._normalize(cf) + 0.45 * self._normalize(content)
        score[idx] = -1
        indices = np.argsort(score)[::-1]

        results = []
        for candidate in indices:
            if score[candidate] < 0:
                continue
            payload = self._movie_payload(self.movies.iloc[candidate])
            payload["recommendation_score"] = round(float(score[candidate]), 4)
            results.append(payload)
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def _normalize(values):
        values = np.asarray(values, dtype=float)
        low, high = np.nanmin(values), np.nanmax(values)
        if not np.isfinite(low) or not np.isfinite(high) or high <= low:
            return np.zeros_like(values)
        return (values - low) / (high - low)

    @staticmethod
    def _movie_payload(row):
        return {
            "movieId": int(row["movieId"]),
            "title": str(row["title"]),
            "genres": str(row["genres"]),
            "average_rating": round(float(row.get("average_rating", 0)), 2),
            "rating_count": int(row.get("rating_count", 0)),
        }
