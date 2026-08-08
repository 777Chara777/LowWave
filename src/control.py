# src/control.py
import asyncio
from typing import List, Dict, Any, Optional, TYPE_CHECKING

import os
import random
import time
import numpy as np

if TYPE_CHECKING:
    from . import LowWaveManager

class LowWaveControl:
    def __init__(self, manager) -> None:
        self.manager: "LowWaveManager" = manager
        self.playlist_queue: List[str] = []

        self.previous_track_info: Optional[Dict[str, Any]] = None
        self.current_track_info: Dict[str, Any] = {
            "title": "Ожидание трека...",
            "artist": "LowWave Radio",
            "video_id": None,
            "liked": False,
            "lyrics": []
        }
        self.next_track_info: Optional[Dict[str, Any]] = None
        self.next_pcm_data: Optional[np.ndarray] = None
        self.dj_comment: str = "Радиостанция инициализирована."

        self.track_start_time: float = time.time()

    async def add_to_queue(self, video_id: str):
        """Добавить трек в очередь заказа"""
        self.playlist_queue.append(video_id)
        if not self.current_track_info["video_id"]:
            await self.prepare_next_track()
            await self.play_prepared_track()

    async def prepare_next_track(self) -> Dict[str, Any]:
        """Этап 1: Подготовка метаданных и буферизация PCM (без отправки в микшер)"""
        if self.playlist_queue:
            next_id = self.playlist_queue.pop(0)
        else:
            files = [x.replace(".webm", "") for x in os.listdir("live_cache/") if x.endswith(".webm")]
            next_id = random.choice(files) if files else "default_id"

        player_service = self.manager.player_service
        
        # Вызываем сетевые запросы асинхронно через asyncio.to_thread
        meta = await asyncio.to_thread(player_service.get_track_info, next_id)
        lyrics = await asyncio.to_thread(player_service.get_track_lyrics, next_id)
        
        self.next_track_info = {
            "video_id": next_id,
            "title": meta.get("title", "Unknown Title"),
            "artist": meta.get("artist", "Unknown Artist"),
            "cover_url": meta.get("cover_url", ""),
            "liked": False,
            "lyrics": lyrics
        }

        self.next_pcm_data = await self.manager.load_track(next_id)
        return self.next_track_info

    async def play_prepared_track(self):
        """Этап 2: Загрузка PCM в микшер, обновление UI и запуск музыки"""
        if not self.next_track_info or self.next_pcm_data is None:
            await self.prepare_next_track()

        if self.next_pcm_data is not None:
            self.manager.music_track.set_pcm_data(self.next_pcm_data)
            self.next_pcm_data = None

        if self.current_track_info["video_id"]:
            self.previous_track_info = self.current_track_info.copy()

        self.current_track_info = self.next_track_info.copy() # type: ignore
        self.next_track_info = None

        self.track_start_time = time.time()

        await self.manager.webwave.broadcast_status()

    def get_playlist(self) -> List[str]:
        return self.playlist_queue

    def get_status(self) -> Dict[str, Any]:
        elapsed = (
            max(0.0, round(time.time() - self.track_start_time, 2))
            if self.track_start_time
            else 0.0
        )

        return {
            "track": self.get_track_info(),
            "next_track": self.get_next_track_info(),
            "dj_comment": self.dj_comment if self.manager.llm.message == "" else self.manager.llm.message,
            "queue_length": len(self.playlist_queue),
            "telemetry": {"weather": "21° СОЛНЦЕ"},
            # "llm_message": self.manager.llm.message,
            "elapsed": elapsed,
            "lyrics": self.current_track_info.get("lyrics", ["Текст отсутствует"])
        }

    def get_previous_track_info(self) -> Optional[Dict[str, Any]]:
        return self.previous_track_info

    def get_next_track_info(self) -> Optional[Dict[str, Any]]:
        return self.next_track_info

    def get_track_info(self) -> Dict[str, Any]:
        return self.current_track_info

    async def search_tracks(self, query: str) -> List[Dict[str, Any]]:
        """Поиск треков через PlayerService для выдачи списком на фронтенд"""
        if not query:
            return []
        return await asyncio.to_thread(self.manager.player_service.search_tracks, query)

