import asyncio
import time
import numpy as np
from typing import List

from .AudioTrack import (AudioTrack as ClassAudioTrack, AudioDecoder )


class LowSoundMixer:
    """Многодорожечный микшер на базе numpy"""
    def __init__(self, sample_rate: int = 44100, chunk_size: int = 4096, channels: int = 2, broadcaster=None) -> None:
        self.sample_rate = sample_rate
        self.chunk_size = chunk_size
        self.channels = channels
        self.tracks: List[ClassAudioTrack] = []
        self.broadcaster = broadcaster
        
        self._queue: asyncio.Queue[bytes] | None = None

    @property
    def quele(self) -> asyncio.Queue[bytes]:
        if self._queue is None:
            self._queue = asyncio.Queue(maxsize=50)
        return self._queue

    def add_track(self, track: ClassAudioTrack):
        self.tracks.append(track)

    def get_quele(self):
        return self.quele

    async def start_mixing_loop(self):
        chunk_duration = self.chunk_size / self.sample_rate
        total_samples = self.chunk_size * self.channels
        next_tick = time.monotonic()

        try:
            while True:
                mixed_buffer = np.zeros(total_samples, dtype=np.float32)

                for track in self.tracks:
                    chunk = track.get_next_chunk(self.chunk_size)
                    mixed_buffer += chunk.astype(np.float32)

                mixed_buffer = np.clip(mixed_buffer, -32768, 32767)
                final_chunk = mixed_buffer.astype(np.int16).tobytes()

                if self.broadcaster:
                    if asyncio.iscoroutinefunction(self.broadcaster):
                        await self.broadcaster(final_chunk)
                    else:
                        self.broadcaster(final_chunk)

                next_tick += chunk_duration
                sleep_time = next_tick - time.monotonic()

                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                else:
                    next_tick = time.monotonic()
                    await asyncio.sleep(0)
        except asyncio.CancelledError:
            pass