from __future__ import annotations

from pathlib import Path
from urllib.request import Request, urlopen
from zipfile import ZipFile, is_zipfile
import io

import joblib
import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
ARTIFACT_DIR = ROOT / "artifacts"
ZIP_URL = "https://files.grouplens.org/datasets/movielens/ml-latest-small.zip"
ZIP_PATH = DATA_DIR / "ml-latest-small.zip"


def download_dataset():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    required = DATA_DIR / "ml-latest-small" / "ratings.csv"
    if required.exists():
        print("MovieLens dataset already exists.", flush=True)
        return

    print("Downloading MovieLens latest-small from GroupLens...", flush=True)
    request = Request(ZIP_URL, headers={"User-Agent": "DA4-Movie-Recommender/1.0"})
    with urlopen(request, timeout=180) as response:
        payload = response.read()

    if not zipfile_is_valid(payload):
        raise RuntimeError("The MovieLens download is not a valid ZIP archive.")

    with ZipFile(io.BytesIO(payload)) as archive:
        expected = {
            "ml-latest-small/ratings.csv",
            "ml-latest-small/movies.csv",
            "ml-latest-small/tags.csv",
        }
        names = set(archive.namelist())
        missing = expected - names
        if missing:
            raise RuntimeError(f"MovieLens ZIP is missing files: {sorted(missing)}")
        archive.extractall(DATA_DIR)

    if not required.exists():
        raise RuntimeError("Dataset extraction finished but ratings.csv was not found.")
    print("MovieLens dataset downloaded and extracted.", flush=True)


def zipfile_is_valid(payload: bytes) -> bool:
    return payload[:4] == b"PK\x03\x04" or payload[:4] == b"PK\x05\x06"


def main():
    download_dataset()
    folder = DATA_DIR / "ml-latest-small"
    ratings = pd.read_csv(folder / "ratings.csv")
    movies = pd.read_csv(folder / "movies.csv")
    tags = pd.read_csv(folder / "tags.csv")

    required_ratings = {"userId", "movieId", "rating"}
    required_movies = {"movieId", "title", "genres"}
    if not required_ratings.issubset(ratings.columns):
        raise ValueError("ratings.csv is missing required columns.")
    if not required_movies.issubset(movies.columns):
        raise ValueError("movies.csv is missing required columns.")

    rating_stats = ratings.groupby("movieId")["rating"].agg(
        average_rating="mean", rating_count="count"
    )
    movies = movies.merge(rating_stats, on="movieId", how="left")
    movies[["average_rating", "rating_count"]] = movies[
        ["average_rating", "rating_count"]
    ].fillna(0)

    movie_ids = movies["movieId"].astype(int).tolist()
    user_ids = sorted(ratings["userId"].astype(int).unique().tolist())
    movie_to_idx = {movie_id: idx for idx, movie_id in enumerate(movie_ids)}
    user_to_idx = {user_id: idx for idx, user_id in enumerate(user_ids)}
    idx_to_movie = {idx: movie_id for movie_id, idx in movie_to_idx.items()}

    rows = ratings["userId"].map(user_to_idx).to_numpy()
    cols = ratings["movieId"].map(movie_to_idx)
    valid = cols.notna().to_numpy()
    user_item = csr_matrix(
        (
            ratings.loc[valid, "rating"].to_numpy(dtype=np.float32),
            (rows[valid], cols[valid].to_numpy(dtype=int)),
        ),
        shape=(len(user_ids), len(movie_ids)),
        dtype=np.float32,
    )

    # Item-based collaborative filtering: nearest movies by user-rating patterns.
    item_user = user_item.T.tocsr()
    neighbors = min(31, len(movie_ids))
    nn = NearestNeighbors(metric="cosine", algorithm="brute", n_neighbors=neighbors)
    nn.fit(item_user)
    distances, indices = nn.kneighbors(item_user)
    sim_rows, sim_cols, sim_data = [], [], []
    for item_idx, (dist_row, index_row) in enumerate(zip(distances, indices)):
        for distance, neighbor_idx in zip(dist_row, index_row):
            similarity = max(0.0, 1.0 - float(distance))
            if item_idx != int(neighbor_idx) and similarity > 0:
                sim_rows.append(item_idx)
                sim_cols.append(int(neighbor_idx))
                sim_data.append(similarity)
    item_similarity = csr_matrix(
        (sim_data, (sim_rows, sim_cols)),
        shape=(len(movie_ids), len(movie_ids)),
        dtype=np.float32,
    )

    # Content-based representation from genres and user-applied tags.
    tag_text = tags.groupby("movieId")["tag"].apply(
        lambda values: " ".join(str(value) for value in values)
    )
    tag_text = tag_text.to_dict()
    content_text = []
    for _, movie in movies.iterrows():
        genre_text = str(movie["genres"]).replace("|", " ")
        content_text.append(
            f"{genre_text} {tag_text.get(int(movie['movieId']), '')}".strip()
        )
    vectorizer = TfidfVectorizer(
        stop_words="english", ngram_range=(1, 2), min_df=1, max_features=20000
    )
    content_features = vectorizer.fit_transform(content_text).tocsr()

    popularity = np.log1p(movies["rating_count"].to_numpy(dtype=np.float32))
    ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    artifact = {
        "movies": movies,
        "user_item": user_item,
        "item_similarity": item_similarity,
        "content_features": content_features,
        "movie_to_idx": movie_to_idx,
        "user_to_idx": user_to_idx,
        "idx_to_movie": idx_to_movie,
        "popularity": popularity,
        "mean_rating": float(ratings["rating"].mean()),
        "dataset": "MovieLens latest-small",
    }
    target = ARTIFACT_DIR / "movie_recommender.joblib"
    joblib.dump(artifact, target, compress=3)

    summary = {
        "dataset": "MovieLens latest-small",
        "ratings": int(len(ratings)),
        "tag_applications": int(len(tags)),
        "movies": int(len(movies)),
        "users": int(len(user_ids)),
        "average_rating": round(float(ratings["rating"].mean()), 4),
        "rating_scale": "0.5 to 5.0",
        "models": [
            "Item-based Collaborative Filtering",
            "TF-IDF Content-Based Filtering",
            "Hybrid Recommendation",
        ],
    }
    (ARTIFACT_DIR / "dataset_summary.json").write_text(
        pd.Series(summary).to_json(force_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Saved trained recommender to {target}", flush=True)
    print(summary, flush=True)


if __name__ == "__main__":
    main()
