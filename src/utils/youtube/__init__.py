import os
import yt_dlp
import asyncio
import json
from ytmusicapi import YTMusic

from typing import Optional, List, Dict, Any

class LowWavePlayerService:
    def __init__(self, cache_dir="./lowwave_cache", auth=None):
        """
        Инициализация сервиса для работы с YouTube Music и потоками.
        :param auth: Путь к файлу авторизации (например, "headers_auth.json" или "oauth.json") либо None.
        """
        self.auth = auth
        self.cache_dir = cache_dir
        os.makedirs(self.cache_dir, exist_ok=True)

    @property
    def yt(self):
        """Ленивая инициализация YTMusic с поддержкой авторизации, чтобы патч успел её перехватить"""
        return YTMusic(self.auth)

    def search_track(self, query: str):
        """
        Поиск трека по запросу (название, артист и т.д.).
        Возвращает словарь с метаданными.
        """
        results = self.yt.search(query, filter="songs", limit=1)
        if not results:
            return None
        
        song = results[0]
        return {
            "video_id": song.get("videoId"),
            "title": song.get("title"),
            "artists": ", ".join([a["name"] for a in song.get("artists", [])]),
            "album": song.get("album", {}).get("name"),
            "duration": song.get("duration"),
            "thumbnails": song.get("thumbnails", [])
        }

    def search_tracks(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Поиск нескольких треков по запросу для выпадающего списка WebSocket.
        """
        try:
            results = self.yt.search(query, filter="songs", limit=limit)
            if not results:
                return []

            formatted = []
            for song in results:
                artists_raw = song.get("artists", [])
                artists_str = ", ".join([a["name"] for a in artists_raw]) if isinstance(artists_raw, list) else "Неизвестен"
                
                formatted.append({
                    "id": song.get("videoId"),
                    "title": song.get("title", "Без названия"),
                    "artist": artists_str
                })
            return formatted
        except Exception as e:
            print(f"[PlayerService] Ошибка поиска: {e}")
            return []

    def get_track_lyrics(self, video_id: str) -> List[Dict[str, Any]]:
        """Получение текста песни с таймкодами"""
        try:
            watch_playlist = self.yt.get_watch_playlist(videoId=video_id)
            lyrics_id = watch_playlist.get("lyrics")
            if not lyrics_id:
                return [{"time": 0, "text": "Текст песни не найден"}]

            lyrics_data = self.yt.get_lyrics(lyrics_id, timestamps=True) # type: ignore
            raw_lyrics = lyrics_data.get("lyrics", "")

            if isinstance(raw_lyrics, list):
                result = []
                for item in raw_lyrics:
                    if isinstance(item, dict):
                        text = item.get("text") or item.get("line") or ""
                        ms = (
                            item.get("start_time")
                            or item.get("start")
                            or item.get("timestamp")
                            or 0
                        )
                    else:
                        text = getattr(item, "text", getattr(item, "line", ""))
                        ms = getattr(
                            item,
                            "start_time",
                            getattr(item, "start", getattr(item, "timestamp", 0)),
                        )

                    text = str(text).strip()
                    if text:
                        result.append(
                            {
                                "time": round(float(ms) / 1000.0, 2),
                                "text": text,
                            }
                        )

                return result if result else [{"time": 0, "text": "Текст песни пуст"}]

            if isinstance(raw_lyrics, str):
                lines = [
                    line.strip()
                    for line in raw_lyrics.split("\n")
                    if line.strip()
                ]
                return [
                    {"time": round(i * 4.0, 2), "text": line}
                    for i, line in enumerate(lines)
                ]

            return [{"time": 0, "text": "Неизвестный формат текста"}]

        except Exception as e:
            print(f"[PlayerService] Ошибка получения текста: {e}")
            return [{"time": 0, "text": "Не удалось загрузить текст"}]
            

    def get_playlist_tracks(self, playlist_id: str, limit: int = 20):
        """
        Получение списка треков из плейлиста пользователя по его ID.
        """
        try:
            playlist = self.yt.get_playlist(playlist_id, limit=limit)
            if not playlist:
                return []
            
            tracks = []
            raw_tracks = playlist.get("tracks", [])
            if not raw_tracks:
                raw_tracks = playlist.get("contents", [])
                
            for song in raw_tracks:
                if not isinstance(song, dict):
                    continue
                    
                video_id = song.get("videoId") or song.get("id")
                title = song.get("title", "Unknown Title")
                
                artists_raw = song.get("artists", [])
                if isinstance(artists_raw, list):
                    artists_str = ", ".join([a.get("name", "") for a in artists_raw if isinstance(a, dict)])
                else:
                    artists_str = str(artists_raw)

                tracks.append({
                    "video_id": video_id,
                    "title": title,
                    "artists": artists_str,
                    "duration": song.get("duration")
                })
            return tracks
        except Exception as e:
            print(f"Ошибка получения плейлиста: {e}")
            return []
    
    def get_track_info(self, video_id: str) -> Dict[str, Any]:
        """Получение подробных метаданных трека и обложки по его video_id"""
        json_path = os.path.join(self.cache_dir, f"{video_id}.json")

        if os.path.exists(json_path):
            try:
                with open(json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[PlayerService] Ошибка чтения JSON-кэша для {video_id}: {e}")
                
        try:
            song = self.yt.get_song(video_id)
            video_details = song.get("videoDetails", {})
            
            thumbnails = video_details.get("thumbnail", {}).get("thumbnails", [])
            cover_url = thumbnails[-1]["url"] if thumbnails else None

            meta = {
                "video_id": video_id,
                "title": video_details.get("title", f"Track {video_id}"),
                "artist": video_details.get("author", "Неизвестный исполнитель"),
                "cover_url": cover_url
            }

            self.save_metadata_to_json(video_id, meta)
            return meta
        except Exception as e:
            print(f"[PlayerService] Ошибка получения метаданных для {video_id}: {e}")
            return {
                "title": f"Track {video_id}",
                "artist": "LowWave Radio",
                "cover_url": None
            }
        
    def get_playlist_tracks_with_meta(self, playlist_id: str, limit: int = 20):
        """
        Получение списка треков из плейлиста вместе с полной метаинформацией.
        """
        try:
            playlist = self.yt.get_playlist(playlist_id, limit=limit)
            if not playlist:
                return []
            
            tracks = []
            raw_tracks = playlist.get("tracks", [])
            if not raw_tracks:
                raw_tracks = playlist.get("contents", [])
                
            for song in raw_tracks:
                if not isinstance(song, dict):
                    continue
                    
                video_id = song.get("videoId") or song.get("id")
                title = song.get("title", "Unknown Title")
                
                artists_raw = song.get("artists", [])
                if isinstance(artists_raw, list):
                    artists_str = ", ".join([a.get("name", "") for a in artists_raw if isinstance(a, dict)])
                else:
                    artists_str = str(artists_raw)

                tracks.append({
                    "video_id": video_id,
                    "title": title,
                    "artists": artists_str,
                    "album": song.get("album", {}).get("name") if isinstance(song.get("album"), dict) else None,
                    "duration": song.get("duration"),
                    "thumbnails": song.get("thumbnails", [])
                })
            return tracks
        except Exception as e:
            print(f"Ошибка получения плейлиста с метаданными: {e}")
            return []

    def get_streaming_url(self, video_id: str):
        """
        Получение актуальной прямой ссылки на аудиопоток (для аудиоплеера).
        """
        url = f"https://www.youtube.com/watch?v={video_id}"
        ydl_opts = {
            'format': 'best',
            'noplaylist': True,
            'quiet': True,
            'extractor_args': {
                'youtube': {
                    'player_client': ['web', 'android']
                }
            }
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl: # type: ignore
                info = ydl.extract_info(url, download=False)
                return info.get('url')
        except Exception as e:
            print(f"Ошибка получения потоковой ссылки: {e}")
            return None

    def save_metadata_to_json(self, video_id: str, meta_data: Dict[str, Any]):
        """Вспомогательный метод сохранения словаря в JSON-файл"""
        json_path = os.path.join(self.cache_dir, f"{video_id}.json")
        try:
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(meta_data, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"[PlayerService] Ошибка сохранения JSON для {video_id}: {e}")

    def get_user_playlists(self):
        """
        Возвращает список плейлистов пользователя (ID и название).
        Требует авторизации (передачи файла auth в конструктор).
        """
        try:
            playlists = self.yt.get_library_playlists()
            return [
                {"playlist_id": p.get("playlistId"), "title": p.get("title")} 
                for p in playlists
            ]
        except Exception as e:
            print(f"Ошибка получения списка плейлистов: {e}")
            return []

    async def prefetch_track_to_cache(self, video_id: str) -> Optional[str]:
        """Асинхронное скачивание трека в кэш без блокировки event loop"""
        return await asyncio.to_thread(self._download_track_sync, video_id)

    def _download_track_sync(self, video_id: str) -> Optional[str]:
        for ext in ['webm', 'm4a', 'mp3', 'opus', 'ogg']:
            cached_file = os.path.join(self.cache_dir, f"{video_id}.{ext}")
            if os.path.exists(cached_file):
                print(f"[PlayerService] Файл {video_id} найден в кэше: {cached_file}")
                return cached_file

        output_template = os.path.join(self.cache_dir, f"{video_id}.%(ext)s")
        ydl_opts = {
            'format': 'bestaudio/best',
            'outtmpl': output_template,
            'quiet': True,
            'noplaylist': True,
        }
        url = f"https://www.youtube.com/watch?v={video_id}"
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl: # type: ignore
                info = ydl.extract_info(url, download=True)
                return ydl.prepare_filename(info)
        except Exception as e:
            print(f"[PlayerService] Ошибка кэширования: {e}")
            return None

    def cleanup_cache(self, active_video_id: str):
        """
        Очистка кэша от всех файлов, кроме текущего активного трека.
        """
        for filename in os.listdir(self.cache_dir):
            if active_video_id not in filename:
                try:
                    os.remove(os.path.join(self.cache_dir, filename))
                except OSError:
                    pass