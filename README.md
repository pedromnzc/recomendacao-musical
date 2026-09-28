# Sistema de Recomendação Musical com FastAPI

API com 5 abordagens de recomendação sobre o dataset `data/music_cleaned.csv` (586 músicas do Top Spotify 2010–2019, gerado por `app/data.py` a partir de `data/music.csv`).

| # | Endpoint | Método | Abordagem |
|---|----------|--------|-----------|
| 1 | `/recommendations/content-based/{song_title}` | GET | Similaridade de cosseno das características musicais |
| 2 | `/recommendations/genre-artist` | POST | Mesmo gênero/artista, ordenado por popularidade |
| 3 | `/recommendations/collaborative/{user_id}` | GET | Co-ocorrência entre usuários fictícios |
| 4 | `/recommendations/hybrid` | POST | Combinação ponderada de conteúdo + colaborativo |
| 5 | `/recommendations/popular` | GET | Mais populares, filtradas por ano/gênero |

## Como rodar

Todos os comandos são executados **na raiz do projeto**, porque o CSV é lido por caminho relativo.

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows  (Linux/Mac: source .venv/bin/activate)
pip install -r requirements.txt

uvicorn app.main:app --reload
```

- Swagger (documentação interativa): http://127.0.0.1:8000/docs
- Testes automatizados: `pytest -q`

### Rodando com Docker

Com o Docker Desktop aberto, na raiz do projeto:

```bash
docker compose up --build
```

1. O serviço `tests` instala as dependências e roda o `pytest -v`. Os resultados aparecem no log.
2. Se todos os testes passarem, o serviço `api` sobe a API em http://127.0.0.1:8000/docs. Se algum falhar, a API não sobe.

Para parar: `Ctrl+C` e depois `docker compose down`.

## Características usadas

`bpm, energy, danceability, loudness, liveness, valence, length, acousticness, speechiness`. Elas são normalizadas com `MinMaxScaler` para ficar entre 0 e 1, e a similaridade entre músicas é o cosseno desses vetores.

## Usuários fictícios (filtro colaborativo)

| Usuário | Músicas curtidas |
|---------|------------------|
| user1 | Shape of You, Thinking out Loud, Someone You Loved, Memories, Stay With Me |
| user2 | Shape of You, Memories, Girls Like You (feat. Cardi B), Sugar, Attention |
| user3 | Thinking out Loud, Stay With Me, All of Me, Someone You Loved, I'm Not The Only One |
| user4 | Wake Me Up, Closer, Don't Let Me Down, In the Name of Love, Silence |
| user5 | Closer, Happier, Silence, One Kiss (with Dua Lipa), Wake Me Up |
| user6 | Starboy, The Hills, I Feel It Coming, Love On The Brain, That's What I Like |
| user7 | Havana (feat. Young Thug), New Rules, IDGAF, One Kiss (with Dua Lipa), Starboy |
| user8 | Treat You Better, Love Yourself, Sorry, There's Nothing Holdin' Me Back, Memories |

---

## 1. Recomendação baseada em conteúdo

`GET /recommendations/content-based/{song_title}`

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `limit` | int | 5 | Quantidade de recomendações |
| `weights` | JSON (string) | — | Peso de cada característica, ex.: `{"energy": 2, "bpm": 0.5}`. As características que não forem informadas ficam com peso 1. |

A busca pelo título ignora maiúsculas e minúsculas. A música buscada não aparece nas recomendações.

```bash
curl "http://127.0.0.1:8000/recommendations/content-based/Memories?limit=2"
```

```json
{
  "song": "Memories",
  "artist": "Maroon 5",
  "weights": null,
  "recommendations": [
    {"title": "Tee Shirt - Soundtrack Version", "artist": "Birdy", "genre": "neo mellow", "year": 2014, "similarity": 0.99},
    {"title": "Night Changes", "artist": "One Direction", "genre": "boy band", "year": 2015, "similarity": 0.962}
  ]
}
```

Com pesos:

```bash
curl -G "http://127.0.0.1:8000/recommendations/content-based/Memories" --data-urlencode 'weights={"energy": 2, "bpm": 0.5}'
```

Erros: `404` quando a música não existe; `400` quando `weights` não é JSON, tem uma característica desconhecida ou tem um peso que não é número.

## 2. Recomendação por gênero/artista

`POST /recommendations/genre-artist`

Devolve músicas cujo gênero **ou** artista contém o texto informado. As músicas do artista buscado vêm primeiro e, dentro de cada grupo, a ordem é por popularidade.

```bash
curl -X POST "http://127.0.0.1:8000/recommendations/genre-artist" \
     -H "Content-Type: application/json" \
     -d '{"genre": "pop", "artist": "Ed Sheeran", "limit": 3}'
```

```json
{
  "genre": "pop",
  "artist": "Ed Sheeran",
  "total_found": 475,
  "recommendations": [
    {"title": "South of the Border (feat. Camila Cabello & Cardi B)", "artist": "Ed Sheeran", "genre": "pop", "year": 2019, "popularity": 92},
    {"title": "Shape of You", "artist": "Ed Sheeran", "genre": "pop", "year": 2017, "popularity": 87},
    {"title": "Beautiful People (feat. Khalid)", "artist": "Ed Sheeran", "genre": "pop", "year": 2019, "popularity": 86}
  ]
}
```

Erros: `400` quando não se informa nem `genre` nem `artist`; `404` quando nada é encontrado.

## 3. Filtro colaborativo

`GET /recommendations/collaborative/{user_id}?limit=5`

Usa a lógica "quem gostou disso também gostou daquilo". Na inicialização é montada uma contagem de **co-ocorrências**: `co_occurrence[A][B]` é o número de usuários que curtiram A e B. O score de uma música M para o usuário é a soma de `co_occurrence[s][M]` para cada música `s` que ele curtiu. Músicas já curtidas são excluídas e os empates são decididos pela popularidade.

```bash
curl "http://127.0.0.1:8000/recommendations/collaborative/user1"
```

```json
{
  "user_id": "user1",
  "liked_songs": ["Shape of You", "Thinking out Loud", "Someone You Loved", "Memories", "Stay With Me"],
  "recommendations": [
    {"title": "All of Me", "artist": "John Legend", "genre": "neo mellow", "year": 2014, "score": 3},
    {"title": "I'm Not The Only One", "artist": "Sam Smith", "genre": "pop", "year": 2015, "score": 3},
    {"title": "Attention", "artist": "Charlie Puth", "genre": "dance pop", "year": 2018, "score": 2},
    {"title": "Girls Like You (feat. Cardi B)", "artist": "Maroon 5", "genre": "pop", "year": 2019, "score": 2},
    {"title": "Sugar", "artist": "Maroon 5", "genre": "pop", "year": 2015, "score": 2}
  ]
}
```

Por que esse resultado: o user3 tem 3 músicas em comum com o user1 (Thinking out Loud, Stay With Me e Someone You Loved), então as outras músicas dele recebem +3. O user2 tem 2 em comum (Shape of You e Memories), e as outras músicas dele recebem +2.

Erros: `404` quando o usuário não existe.

## 4. Recomendação híbrida

`POST /recommendations/hybrid`

```
score = content_weight * content_score + collab_weight * collab_score
```

- `content_score`: cosseno entre `song_title` e cada música (0 a 1).
- `collab_score`: score colaborativo de `user_id` dividido pelo maior score (0 a 1).
- Os pesos são normalizados para somar 1. A música de referência e as músicas já curtidas pelo usuário ficam fora das recomendações.

```bash
curl -X POST "http://127.0.0.1:8000/recommendations/hybrid" \
     -H "Content-Type: application/json" \
     -d '{"song_title": "Memories", "user_id": "user1", "content_weight": 0.7, "collab_weight": 0.3, "limit": 3}'
```

```json
{
  "song": "Memories",
  "user_id": "user1",
  "content_weight": 0.7,
  "collab_weight": 0.3,
  "recommendations": [
    {"title": "I'm Not The Only One", "artist": "Sam Smith", "genre": "pop", "year": 2015, "content_score": 0.956, "collab_score": 1.0, "score": 0.969},
    {"title": "All of Me", "artist": "John Legend", "genre": "neo mellow", "year": 2014, "content_score": 0.902, "collab_score": 1.0, "score": 0.932},
    {"title": "Girls Like You (feat. Cardi B)", "artist": "Maroon 5", "genre": "pop", "year": 2019, "content_score": 0.948, "collab_score": 0.667, "score": 0.863}
  ]
}
```

Erros: `404` quando a música ou o usuário não existe; `400` quando algum peso é negativo ou os dois são zero.

## 5. Recomendação por popularidade/ano

`GET /recommendations/popular`

| Parâmetro | Tipo | Padrão | Descrição |
|-----------|------|--------|-----------|
| `year` | int | — | Ano exato (2010–2019) |
| `genre` | str | — | Parte do nome do gênero (ex.: `pop` também encontra `dance pop`) |
| `limit` | int | 5 | Quantidade de resultados |

```bash
curl "http://127.0.0.1:8000/recommendations/popular?year=2019&genre=pop&limit=3"
```

```json
{
  "year": 2019,
  "genre": "pop",
  "total_found": 21,
  "recommendations": [
    {"title": "Memories", "artist": "Maroon 5", "genre": "pop", "year": 2019, "popularity": 99},
    {"title": "Lose You To Love Me", "artist": "Selena Gomez", "genre": "dance pop", "year": 2019, "popularity": 97},
    {"title": "Someone You Loved", "artist": "Lewis Capaldi", "genre": "pop", "year": 2019, "popularity": 96}
  ]
}
```

Erros: `404` quando nenhuma música atende aos filtros.
