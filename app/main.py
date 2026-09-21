from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler
import numpy as np
import json

app = FastAPI()

df = pd.read_csv("data/music_cleaned.csv")

features = ['bpm', 'energy', 'danceability', 'loudness', 'liveness', 'valence', 'length', 'acousticness', 'speechiness']
scaler = MinMaxScaler()
features_scaled = scaler.fit_transform(df[features])

similarity_matrix = cosine_similarity(features_scaled)

class GenreArtistRequest(BaseModel):
    genre: Optional[str] = None
    artist: Optional[str] = None
    limit: int = 5

class HybridRequest(BaseModel):
    song_title: str
    user_id: str
    content_weight: float = 0.7
    collab_weight: float = 0.3
    limit: int = 5

@app.get("/recommendations/content-based/{song_title}")
async def content_based_recommendations(song_title: str, limit: int = 5, weights: Optional[str] = None):

    try:
        idx = df[df["title"].str.lower() == song_title.lower()].index[0]
    except IndexError:
        raise HTTPException(status_code=404, detail=f"Música '{song_title}' não encontrada")

    if weights:
        try:
            weights_dict = json.loads(weights)
        except json.JSONDecodeError:
            raise HTTPException(status_code=400, detail='weights deve ser um JSON, ex.: {"energy": 0.5, "bpm": 0.5}')

        invalid = [name for name in weights_dict if name not in features]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Características inválidas: {invalid}. Use: {features}")
        
        try:
            weight_list = [float(weights_dict.get(name, 1.0)) for name in features]
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Os pesos devem ser números")
        weighted = features_scaled * weight_list

        row_scores = cosine_similarity(weighted[idx:idx+1], weighted)[0]
    else:
        row_scores = similarity_matrix[idx]
  
    scores = list(enumerate(row_scores))
    scores = sorted(scores, key=lambda x: x[1], reverse=True)
    scores = [s for s in scores if s[0] != idx][:limit]

    song_indices = [i[0] for i in scores]

    result = df.iloc[song_indices][["title", "artist", "genre", "year"]].copy()
    result["similarity"] = [round(i[1], 3) for i in scores]

    return {
        "song": df.loc[idx, "title"],
        "artist": df.loc[idx, "artist"],
        "weights": weights_dict if weights else None,
        "recommendations": result.to_dict(orient="records"),
    }

@app.post("/recommendations/genre-artist")
async def genre_artist_recommendations(request: GenreArtistRequest):
    if not request.genre and not request.artist:
        raise HTTPException(status_code=400, detail="Informe pelo menos 'genre' ou 'artist'")

    # 2. Começa com "nenhuma música selecionada" (uma coluna só de False)
    genre_mask = pd.Series(False, index=df.index)
    artist_mask = pd.Series(False, index=df.index)

    if request.genre:
        genre_mask = df["genre"].str.lower().str.contains(request.genre.lower(), regex=False)
    if request.artist:
        artist_mask = df["artist"].str.lower().str.contains(request.artist.lower(), regex=False)

    mask = genre_mask | artist_mask

    result = df[mask].copy()
    result["artist_match"] = artist_mask[mask]  # True para as músicas do artista buscado

    # ordena primeiro por artist_match (True antes de False) e, dentro de cada grupo, por popularidade
    result = result.sort_values(["artist_match", "popularity"], ascending=[False, False]).head(request.limit)

    if result.empty:
        raise HTTPException(status_code=404, detail="Nenhuma música encontrada para esse gênero/artista")

    return {
        "genre": request.genre,
        "artist": request.artist,
        "total_found": int(mask.sum()),
        "recommendations": result[["title", "artist", "genre", "year", "popularity"]].to_dict(orient="records"),
    }