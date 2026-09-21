import pandas as pd

df = pd.read_csv("data/music.csv")
df_cleaned = df.copy()

df_cleaned.rename(columns={
    'the genre of the track': 'genre',
    'Beats.Per.Minute -The tempo of the song': 'bpm',
    'Energy- The energy of a song - the higher the value, the more energtic': 'energy',
    'Danceability - The higher the value, the easier it is to dance to this song': 'danceability',
    'Loudness/dB - The higher the value, the louder the song': 'loudness',
    'Liveness - The higher the value, the more likely the song is a live recording': 'liveness',
    'Valence - The higher the value, the more positive mood for the song': 'valence',
    'Length - The duration of the song': 'length',
    'Acousticness - The higher the value the more acoustic the song is': 'acousticness',
    'Speechiness - The higher the value the more spoken word the song contains': 'speechiness',
    'Popularity- The higher the value the more popular the song is': 'popularity'
}, inplace=True)

df_cleaned = df_cleaned[df_cleaned['bpm'] > 0]

df_cleaned.sort_values('popularity', ascending=False, inplace=True)
df_cleaned.drop_duplicates(subset=['title', 'artist'], keep='first', inplace=True)

df_cleaned.to_csv("data/music_cleaned.csv", index=False)
print(df_cleaned.head())