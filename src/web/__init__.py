import asyncio
import struct
import uvicorn
import json
import os
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse, HTMLResponse

import typing
if typing.TYPE_CHECKING:
    from src.utils.lowmixer import LowSoundMixer

from typing import Optional, Any

def create_wav_header(sample_rate: int = 44100, channels: int = 1) -> bytes:
    """Генерирует заголовок WAV для бесконечного потока PCM 16-bit."""
    return struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        0xFFFFFFFF,
        b"WAVE",
        b"fmt ",
        16,
        1,
        channels,
        sample_rate,
        sample_rate * channels * 2,
        channels * 2,
        16,
        b"data",
        0xFFFFFFFF,
    )

class WebWave:

    def __init__(self) -> None:
        self.app = FastAPI()
        self.listeners: set[asyncio.Queue[bytes]] = set()
        self.control: Optional[Any] = None
        self.active_websockets: list[WebSocket] = []
        self._register_routes()

    
    def broadcast_chunk(self, chunk: bytes):
        """Рассылка байтов всем подключенным слушателям."""
        for queue in list(self.listeners):
            try:
                queue.put_nowait(chunk)
            except asyncio.QueueFull:
                pass

    async def broadcast_status(self):
        """Разослать всем WebSocket-клиентам актуальное состояние"""
        if not self.control:
            return
        status = json.dumps(self.control.get_status())
        for ws in self.active_websockets:
            try:
                await ws.send_text(status)
            except Exception:
                pass

    def set_control(self, control_instance):
        """Привязываем контроллер к веб-серверу"""
        self.control = control_instance

    def _register_routes(self):

        @self.app.get("/stream")
        async def radio_stream():
            queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=100)
            self.listeners.add(queue)

            async def stream_generator():
                try:
                    yield create_wav_header(sample_rate=44100, channels=2)

                    # (0.5 сек для СТЕРЕО: 44100 * 0.5 * 2 канала * 2 байта = 88200 байт)
                    preroll_silence = b'\x00' * (44100 * 2)
                    yield preroll_silence

                    while True:
                        chunk = await queue.get()
                        yield chunk
                except asyncio.CancelledError:
                    pass
                finally:
                    self.listeners.discard(queue)

            return StreamingResponse(
                stream_generator(),
                media_type="audio/wav",
                headers={
                    "Content-Disposition": "inline",
                    "Cache-Control": "no-store, no-cache, must-revalidate, private",
                    "Pragma": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                    "icy-name": "My Radio",
                    "icy-genre": "Music",
                    "icy-pub": "1",
                },
            )

        @self.app.get("/", response_class=HTMLResponse)
        async def get_index():
            """Отдает ретро HTML-шаблон плеера"""
            
            with open(os.path.join("src", "web", "template", "index.html"), "r", encoding="utf-8") as f:
                return f.read()

        @self.app.get("/api/playlist")
        async def get_playlist():
            """Получить очередь проигрывания"""
            if self.control:
                return {"queue": self.control.get_playlist()}
            return {"queue": []}

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """Вебсокет для Live-обновления интерфейса и приема заказов"""
            await websocket.accept()
            self.active_websockets.append(websocket)
            
            if self.control:
                await websocket.send_text(json.dumps(self.control.get_status()))

            try:
                while True:
                    data = await websocket.receive_json()
                    action = data.get("action")

                    if action == "request" and self.control:
                        song_id = data.get("song")
                        await self.control.add_to_queue(song_id)
                        await self.broadcast_status()

                    elif action == "like" and self.control:
                        self.control.current_track_info["liked"] = data.get("liked", False)
                        await self.broadcast_status()

            except WebSocketDisconnect:
                self.active_websockets.remove(websocket)

    def run(self, host: str = "0.0.0.0", port: int = 8000):
        uvicorn.run(self.app, host=host, port=port, log_level="info")