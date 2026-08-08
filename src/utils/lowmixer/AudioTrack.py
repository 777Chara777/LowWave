import numpy as np
import asyncio
import os

import subprocess

from .HookManager import HookManager

class AudioDecoder:
    """Отдельный сервис для декодирования любых аудиофайлов в PCM via FFmpeg"""
    @staticmethod
    async def decode_file_to_pcm(file_path: str, sample_rate: int = 44100) -> np.ndarray:
        if not os.path.exists(file_path):
            print(f"[AudioDecoder] Файл не найден: {file_path}")
            return np.array([], dtype=np.int16)

        cmd = [
            'ffmpeg', '-i', file_path,
            '-f', 's16le',
            '-acodec', 'pcm_s16le',
            '-ar', str(sample_rate),
            '-ac', '2', # Стерео
            'pipe:1'
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL
        )
        raw_bytes, _ = await process.communicate()
        return np.frombuffer(raw_bytes, dtype=np.int16)

class AudioTrack:
    def __init__(self, name: str, sample_rate: int = 44100, channels: int = 2):
        self.name = name
        self.sample_rate = sample_rate
        self.channels = channels
        self.hook_manager = HookManager()
        
        self.total_frames = 0
        self.current_frame = 0
        self._hook_triggered = False
        self._end_hook_triggered = False

        self.volume = 1.0
        self.target_volume = 1.0

        self.pcm_data = np.array([], dtype=np.int16)

    def set_pcm_data(self, pcm_data: np.ndarray):
        """Загрузка готового массива PCM данных (например, целого музыкального трека)"""
        self.pcm_data = pcm_data
        self.total_frames = len(pcm_data) // self.channels
        self.current_frame = 0
        self._hook_triggered = False
        self._end_hook_triggered = False
        print(f"[AudioTrack] Дорожка '{self.name}': загружено {self.total_frames} сэмплов.")

    def append_pcm_bytes(self, raw_bytes: bytes):
        new_samples = np.frombuffer(raw_bytes, dtype=np.int16)
        if len(self.pcm_data) == 0:
            self.pcm_data = new_samples
        else:
            self.pcm_data = np.concatenate([self.pcm_data, new_samples])
        self.total_frames = len(self.pcm_data) // self.channels

    def get_next_chunk(self, frame_size: int) -> np.ndarray:
        """Синхронный метод получения чанка без блокировки asyncio!"""
        sample_size = frame_size * self.channels
        
        if len(self.pcm_data) == 0 or self.current_frame >= self.total_frames:
            return np.zeros(sample_size, dtype=np.int16)

        start_sample = self.current_frame * self.channels
        end_sample = start_sample + sample_size
        chunk = self.pcm_data[start_sample:end_sample]

        if len(chunk) < sample_size:
            padding = np.zeros(sample_size - len(chunk), dtype=np.int16)
            chunk = np.concatenate([chunk, padding])

        self.current_frame += frame_size

        if self.volume != self.target_volume:
            self.volume = round(0.9 * self.volume + 0.1 * self.target_volume, 2)

        if self.total_frames > 0 and not self._hook_triggered:
            frames_left = self.total_frames - self.current_frame
            if (frames_left / self.sample_rate) <= 15.0:
                self._hook_triggered = True
                asyncio.create_task(self.hook_manager.trigger("track_near_end", self.name))

        if self.current_frame >= self.total_frames and not self._end_hook_triggered:
            self._end_hook_triggered = True
            asyncio.create_task(self.hook_manager.trigger("track_ended", self.name))

        return (chunk.astype(np.float32) * self.volume).astype(np.int16)
    

    def is_playing(self) -> bool:
        return len(self.pcm_data) > 0 and self.current_frame < self.total_frames