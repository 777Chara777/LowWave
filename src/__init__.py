import numpy as np
import threading
import asyncio
import os
import re

import dotenv
dotenv.load_dotenv()

from src.utils.youtube import LowWavePlayerService
from src.utils.llm import LargeLanguageModel
from src.utils.llm.tts import TTSWorker
from src.utils.lowmixer import LowSoundMixer, ClassAudioTrack, AudioDecoder

from src.control import LowWaveControl
from src.web import WebWave

class LowWaveManager:
    def __init__(self) -> None:
        self.webwave = WebWave()
        self.loop = asyncio.new_event_loop()

        self.mixer = LowSoundMixer(broadcaster=self.webwave.broadcast_chunk)
        self.music_track = ClassAudioTrack("music_track")
        self.voice_track = ClassAudioTrack("voice_track")
        self.sfx_track = ClassAudioTrack("sfx")

        self.mixer.add_track(self.music_track)
        self.mixer.add_track(self.voice_track)

        self.player_service = LowWavePlayerService(cache_dir="./live_cache")

        self.llm = LargeLanguageModel(model_path=os.getenv("LLM_PATH", "llm/model/"))
        self.tts = TTSWorker()

        self.control = LowWaveControl(manager=self)
        self.webwave.set_control(self.control)

        self.music_track.hook_manager.subscribe("track_ended", self.handle_track_ended)
        self.music_track.hook_manager.subscribe("track_near_end", self.handle_track_near_end)

        self.sfx_cache: dict[str, bytes] = {}
        self._llm_task: asyncio.Task | None = None

    async def load_track(self, video_id: str) -> np.ndarray:
        """Загрузка трека по ID и декодирование в PCM без вывода в эфир"""
        print(f"[ДИРИЖЕР] Загружаем трек {video_id} в кэш...")
        file_path = await self.player_service.prefetch_track_to_cache(video_id)
        
        if file_path and os.path.exists(file_path):
            print(f"[ДИРИЖЕР] Декодирование {file_path}...")
            return await AudioDecoder.decode_file_to_pcm(file_path)
        else:
            print(f"[ДИРИЖЕР] Ошибка: не удалось скачать трек {video_id}.")
            return np.array([], dtype=np.int16)

    async def handle_track_ended(self, track_name: str):
        if track_name == "music_track":
            print("[ДИРИЖЕР] Музыка закончилась. Передаем слово ведущему...")

            # await self.control.prepare_next_track()
            
            await self._generate_llm_speech()

            while self.voice_track.is_playing():
                await asyncio.sleep(0.1)

            print("[ДИРИЖЕР] Голос завершил эфир. Запускаем следующий трек...")
            
            await self.control.play_prepared_track()

    async def handle_track_near_end(self, track_name: str):
        if track_name == "music_track":
            print("[ДИРИЖЕР] Музыка заканчивается. Начинаем загружать след песню...")
            await self.control.prepare_next_track()

    async def _generate_llm_speech(self):
        print("[DJ VALERA] Ведущий вышел в эфир...")
        
        prev_track = self.control.get_previous_track_info()
        next_track = self.control.get_next_track_info()

        if prev_track and prev_track.get("video_id") and next_track:
            prompt = (
                f"Только что отгремел трек: {prev_track['title']} — {prev_track['artist']}.\n"
                f"Следующая песня в эфире: {next_track['title']} — {next_track['artist']}.\n"
                f"Прокомментируй прошлый трек и сделай бодрую радио-подводку к следующему треку."
            )
        elif next_track:
            prompt = (
                f"В эфире радио! Следующая песня: {next_track['title']} от {next_track['artist']}.\n"
                f"Сделай яркое приветствие и короткую веселую подводку к этому треку."
            )
        else:
            prompt = "Привет в эфире LowWave Radio! Скоро будет крутой трек."

        sfx_pattern = re.compile(r"\[sfx:([a-zA-Z0-9_]+)\]", re.IGNORECASE)

        async for sentence in self.llm.generate_sentences(prompt): # type: ignore
            sentence_str = sentence.strip()
            if not sentence_str:
                continue

            for match in sfx_pattern.finditer(sentence_str):
                sfx_name = match.group(1).lower()
                if sfx_name in self.sfx_cache:
                    self.sfx_track.append_pcm_bytes(self.sfx_cache[sfx_name])
                else:
                    print(f"[DJ VALERA] Пропущен незакэшированный SFX: {sfx_name}")

            clean_text = sfx_pattern.sub("", sentence_str)

            clean_text = re.sub(r'["«»\[\]]', "", clean_text).strip()

            if clean_text:
                pcm_bytes = await self.tts.text_to_pcm_bytes(clean_text)
                if pcm_bytes:
                    self.voice_track.append_pcm_bytes(pcm_bytes)

    def run(self) -> None:
        server_thread = threading.Thread(
            target=self.webwave.run,
            kwargs={"host": "0.0.0.0", "port": 8000},
            daemon=True
        )
        server_thread.start()
        print("Веб-сервер запущен на порту 8000...")

        async def main_task():
            await self.mixer.start_mixing_loop()

        try:
            self.loop.run_until_complete(main_task())
        except KeyboardInterrupt:
            print("Остановка менеджера...")