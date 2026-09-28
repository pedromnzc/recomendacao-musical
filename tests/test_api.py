from fastapi.testclient import TestClient

from app.main import app, user_likes

client = TestClient(app)


# 1. Conteúdo
def test_content_based():
    r = client.get("/recommendations/content-based/Memories", params={"limit": 3})
    assert r.status_code == 200
    body = r.json()
    assert body["song"] == "Memories"
    assert len(body["recommendations"]) == 3
    assert all(rec["title"] != "Memories" for rec in body["recommendations"])
    similarities = [rec["similarity"] for rec in body["recommendations"]]
    assert similarities == sorted(similarities, reverse=True)

def test_content_based_with_weights():
    r = client.get("/recommendations/content-based/memories", params={"weights": '{"energy": 2, "bpm": 0.5}'})
    assert r.status_code == 200
    assert r.json()["weights"] == {"energy": 2, "bpm": 0.5}

def test_content_based_song_not_found():
    assert client.get("/recommendations/content-based/Musica Que Nao Existe").status_code == 404

def test_content_based_invalid_weights():
    assert client.get("/recommendations/content-based/Memories", params={"weights": "abc"}).status_code == 400
    assert client.get("/recommendations/content-based/Memories", params={"weights": '{"xyz": 1}'}).status_code == 400
    assert client.get("/recommendations/content-based/Memories", params={"weights": '{"bpm": "a"}'}).status_code == 400


# 2. Gênero/Artista
def test_genre_artist():
    r = client.post("/recommendations/genre-artist", json={"genre": "pop", "artist": "Ed Sheeran", "limit": 5})
    assert r.status_code == 200
    recs = r.json()["recommendations"]
    assert len(recs) == 5
    assert recs[0]["artist"] == "Ed Sheeran"

def test_genre_artist_requires_filter():
    assert client.post("/recommendations/genre-artist", json={"limit": 5}).status_code == 400

def test_genre_artist_not_found():
    assert client.post("/recommendations/genre-artist", json={"genre": "genero inexistente"}).status_code == 404


# 3. Colaborativo
def test_collaborative():
    r = client.get("/recommendations/collaborative/user1")
    assert r.status_code == 200
    body = r.json()
    titles = [rec["title"] for rec in body["recommendations"]]
    # All of Me e I'm Not The Only One aparecem com 3 músicas em comum (user3)
    assert titles[:3] == ["All of Me", "I'm Not The Only One", "Attention"]
    assert not set(titles) & set(user_likes["user1"])

def test_collaborative_user_not_found():
    assert client.get("/recommendations/collaborative/user999").status_code == 404


# 4. Híbrido
def test_hybrid():
    r = client.post("/recommendations/hybrid", json={"song_title": "Memories", "user_id": "user1", "limit": 5})
    assert r.status_code == 200
    body = r.json()
    recs = body["recommendations"]
    assert len(recs) == 5
    titles = {rec["title"] for rec in recs}
    assert "Memories" not in titles
    assert not titles & set(user_likes["user1"])
    scores = [rec["score"] for rec in recs]
    assert scores == sorted(scores, reverse=True)

def test_hybrid_only_collab_matches_collaborative():
    r = client.post("/recommendations/hybrid",
                    json={"song_title": "Memories", "user_id": "user1", "content_weight": 0, "collab_weight": 1})
    assert r.json()["recommendations"][0]["collab_score"] == 1.0

def test_hybrid_errors():
    assert client.post("/recommendations/hybrid", json={"song_title": "Nao Existe", "user_id": "user1"}).status_code == 404
    assert client.post("/recommendations/hybrid", json={"song_title": "Memories", "user_id": "user999"}).status_code == 404
    assert client.post("/recommendations/hybrid", json={"song_title": "Memories", "user_id": "user1",
                                                         "content_weight": 0, "collab_weight": 0}).status_code == 400


# 5. Popular
def test_popular():
    r = client.get("/recommendations/popular", params={"year": 2019, "genre": "pop", "limit": 3})
    assert r.status_code == 200
    body = r.json()
    assert [rec["title"] for rec in body["recommendations"]] == ["Memories", "Lose You To Love Me", "Someone You Loved"]
    assert all(rec["year"] == 2019 for rec in body["recommendations"])

def test_popular_no_filters():
    r = client.get("/recommendations/popular")
    assert r.status_code == 200
    assert len(r.json()["recommendations"]) == 5

def test_popular_not_found():
    assert client.get("/recommendations/popular", params={"year": 1950}).status_code == 404
