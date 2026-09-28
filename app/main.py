from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from collections import Counter, defaultdict
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity
from sklearn.preprocessing import MinMaxScaler
import numpy as np
import json

app = FastAPI(
    title="Sistema de Recomendação Musical",
    description="5 abordagens de recomendação: conteúdo, gênero/artista, colaborativa, híbrida e popularidade.",
)

df = pd.read_csv("data/music_cleaned.csv")

features = ['bpm', 'energy', 'danceability', 'loudness', 'liveness', 'valence', 'length', 'acousticness', 'speechiness']
scaler = MinMaxScaler()
features_scaled = scaler.fit_transform(df[features])

similarity_matrix = cosine_similarity(features_scaled)

class GenreArtistRequest(BaseModel):
    genre: Optional[str] = None
    artist: Optional[str] = None
    limit: int = 5

    model_config = {"json_schema_extra": {"examples": [{"genre": "pop", "artist": "Ed Sheeran", "limit": 5}]}}

class HybridRequest(BaseModel):
    song_title: str
    user_id: str
    content_weight: float = 0.7
    collab_weight: float = 0.3
    limit: int = 5

    model_config = {"json_schema_extra": {"examples": [
        {"song_title": "Memories", "user_id": "user1", "content_weight": 0.7, "collab_weight": 0.3, "limit": 5}
    ]}}


def find_song_index(song_title: str):
    matches = df.index[df["title"].str.lower() == song_title.lower()]
    if len(matches) == 0:
        raise HTTPException(status_code=404, detail=f"Música '{song_title}' não encontrada")
    return matches[0]


# Dados fictícios de interação usuário-música ("usuários que gostaram de X")
user_likes = {
    "user1": ["Shape of You", "Thinking out Loud", "Someone You Loved", "Memories", "Stay With Me"],
    "user2": ["Shape of You", "Memories", "Girls Like You (feat. Cardi B)", "Sugar", "Attention"],
    "user3": ["Thinking out Loud", "Stay With Me", "All of Me", "Someone You Loved", "I'm Not The Only One"],
    "user4": ["Wake Me Up", "Closer", "Don't Let Me Down", "In the Name of Love", "Silence"],
    "user5": ["Closer", "Happier", "Silence", "One Kiss (with Dua Lipa)", "Wake Me Up"],
    "user6": ["Starboy", "The Hills", "I Feel It Coming", "Love On The Brain", "That's What I Like"],
    "user7": ["Havana (feat. Young Thug)", "New Rules", "IDGAF", "One Kiss (with Dua Lipa)", "Starboy"],
    "user8": ["Treat You Better", "Love Yourself", "Sorry", "There's Nothing Holdin' Me Back", "Memories"],
}

# converte os títulos em índices do df (falha na inicialização se algum título não existir)
user_like_indices = {user: [find_song_index(title) for title in titles] for user, titles in user_likes.items()}

# co_occurrence[a][b] = quantos usuários gostaram de a e de b ao mesmo tempo
co_occurrence = defaultdict(Counter)
for liked in user_like_indices.values():
    for a in liked:
        for b in liked:
            if a != b:
                co_occurrence[a][b] += 1


def collaborative_scores(user_id: str) -> Counter:
    if user_id not in user_like_indices:
        raise HTTPException(status_code=404, detail=f"Usuário '{user_id}' não encontrado. Use: {list(user_likes)}")

    liked = user_like_indices[user_id]
    scores = Counter()
    for song in liked:
        scores.update(co_occurrence[song])

    # não recomenda o que o usuário já curtiu
    for song in liked:
        scores.pop(song, None)
    return scores


@app.get("/recommendations/content-based/{song_title}", summary="Recomendação baseada em conteúdo")
async def content_based_recommendations(song_title: str, limit: int = 5, weights: Optional[str] = None):
    """
    Músicas mais parecidas com `song_title` pela similaridade de cosseno das características musicais.

    `weights` (opcional) é um JSON com o peso de cada característica, ex.: `{"energy": 2, "bpm": 0.5}`.
    """
    idx = find_song_index(song_title)

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

@app.post("/recommendations/genre-artist", summary="Recomendação por gênero/artista")
async def genre_artist_recommendations(request: GenreArtistRequest):
    """
    Músicas do gênero ou do artista informado, ordenadas por popularidade.
    Músicas do artista buscado aparecem primeiro.
    """
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

@app.get("/recommendations/collaborative/{user_id}", summary="Filtro colaborativo")
async def collaborative_recommendations(user_id: str, limit: int = 5):
    """
    "Quem gostou disso também gostou daquilo": soma quantas vezes cada música aparece junto
    com as músicas curtidas pelo usuário nas listas dos outros usuários (co-ocorrência).
    Usuários disponíveis: user1 a user8.
    """
    scores = collaborative_scores(user_id)

    result = df.loc[list(scores)][["title", "artist", "genre", "year", "popularity"]].copy()
    result["score"] = list(scores.values())

    # empate no score é decidido pela popularidade
    result = result.sort_values(["score", "popularity"], ascending=[False, False]).head(limit)

    return {
        "user_id": user_id,
        "liked_songs": df.loc[user_like_indices[user_id], "title"].tolist(),
        "recommendations": result[["title", "artist", "genre", "year", "score"]].to_dict(orient="records"),
    }

@app.post("/recommendations/hybrid", summary="Recomendação híbrida")
async def hybrid_recommendations(request: HybridRequest):
    """
    Combina a similaridade de conteúdo com `song_title` e o score colaborativo de `user_id`:
    `score = content_weight * content_score + collab_weight * collab_score` (pesos normalizados para somar 1).
    """
    if request.content_weight < 0 or request.collab_weight < 0 or request.content_weight + request.collab_weight == 0:
        raise HTTPException(status_code=400, detail="Os pesos devem ser >= 0 e pelo menos um deve ser maior que 0")

    total_weight = request.content_weight + request.collab_weight
    content_weight = request.content_weight / total_weight
    collab_weight = request.collab_weight / total_weight

    idx = find_song_index(request.song_title)
    scores = collaborative_scores(request.user_id)

    content_scores = similarity_matrix[idx]

    # score colaborativo em 0-1 (divide pelo maior) para ficar na mesma escala do cosseno
    collab_scores = np.zeros(len(df))
    if scores:
        max_score = max(scores.values())
        for song, score in scores.items():
            collab_scores[song] = score / max_score

    final_scores = content_weight * content_scores + collab_weight * collab_scores

    exclude = {idx, *user_like_indices[request.user_id]}
    ranking = [i for i in np.argsort(final_scores)[::-1] if i not in exclude][:request.limit]

    result = df.iloc[ranking][["title", "artist", "genre", "year"]].copy()
    result["content_score"] = content_scores[ranking].round(3)
    result["collab_score"] = collab_scores[ranking].round(3)
    result["score"] = final_scores[ranking].round(3)

    return {
        "song": df.loc[idx, "title"],
        "user_id": request.user_id,
        "content_weight": round(content_weight, 3),
        "collab_weight": round(collab_weight, 3),
        "recommendations": result.to_dict(orient="records"),
    }

@app.get("/recommendations/popular", summary="Recomendação por popularidade/ano")
async def popular_recommendations(year: Optional[int] = None, genre: Optional[str] = None, limit: int = 5):
    """
    Músicas mais populares, com filtro opcional por ano (`year`) e/ou gênero (`genre`).
    """
    # começa com "todas as músicas selecionadas" e vai aplicando os filtros
    mask = pd.Series(True, index=df.index)

    if year is not None:
        mask &= df["year"] == year
    if genre:
        mask &= df["genre"].str.lower().str.contains(genre.lower(), regex=False)

    result = df[mask].sort_values("popularity", ascending=False).head(limit)

    if result.empty:
        raise HTTPException(status_code=404, detail="Nenhuma música encontrada para esse ano/gênero")

    return {
        "year": year,
        "genre": genre,
        "total_found": int(mask.sum()),
        "recommendations": result[["title", "artist", "genre", "year", "popularity"]].to_dict(orient="records"),
    }
