import io
import edge_tts
import av

class TTSWorker:
    def __init__(self, voice: str = "ru-RU-DmitryNeural", rate: str = "+0%", pitch: str = "+0Hz"):
        self.voice = voice
        self.rate = rate
        self.pitch = pitch

    async def text_to_pcm_bytes(self, text: str) -> bytes:
        clean_text = text.strip()
        
        if not clean_text or not any(char.isalnum() for char in clean_text):
            return b""

        communicate = edge_tts.Communicate(
            text=clean_text,
            voice=self.voice,
            rate=self.rate,
            pitch=self.pitch
        )

        mp3_buffer = io.BytesIO()
        try:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    mp3_buffer.write(chunk["data"]) # type: ignore
                    
        except edge_tts.exceptions.NoAudioReceived:
            print(f"[TTS WARNING] Пропущена фраза не вызвавшая генерацию: '{clean_text}'")
            return b""

        mp3_buffer.seek(0)
        
        if mp3_buffer.getbuffer().nbytes == 0:
            return b""

        container = av.open(mp3_buffer)
        resampler = av.AudioResampler(format='s16', layout='stereo', rate=44100)
        
        pcm_bytes = bytearray()
        for frame in container.decode(audio=0): # type: ignore
            resampled_frames = resampler.resample(frame)
            for r_frame in resampled_frames:
                pcm_bytes.extend(r_frame.to_ndarray().tobytes())

        return bytes(pcm_bytes)