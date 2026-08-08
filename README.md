# LowWave 📻

A multi-track real-time audio mixer and streaming server in Python, inspired by "Sub/Wave". The project is designed around the principles of a Digital Audio Workstation (DAW): it supports independent audio tracks (music, voice, effects), mathematical mixing via `numpy`, an event-driven hook system for automation, and live streaming via FastAPI.

---

## 🏗 Project Architecture

* **`MultiTrackMixer`**: A clock generator that pulls chunks from all active tracks in real time, performs mathematical layering using `numpy`, and normalizes volume.
* **`AudioTrack`**: An independent track with its own queue and timeline tracking in samples. It can trigger events (hooks) when approaching the end of a track.
* **`HookManager`**: An event bus (Observer) connecting tracks to the Conductor (`LowWaveManager`) to trigger background tasks (such as track prefetching and LLM + TTS speech generation).
* **`LowWavePlayerService`**: Integration with YouTube Music and `yt_dlp` for searching, caching, and streaming audio[cite: 3].
* **`WebWave`**: An asynchronous FastAPI web server delivering a continuous audio stream (`StreamingResponse`) via the `/stream` endpoint.

---

## 📂 Directory Structure

```text
lowwave/
├── src/
│   ├── utils/
│   │   ├── __init__.py      # YouTube Music service (LowWavePlayerService)
│   │   └── lowmixer.py      # Mixer, tracks, and hook manager
│   ├── web.py               # FastAPI web server and streaming endpoint
│   └── main.py              # Conductor (LowWaveManager)
├── tests/
│   └── test_lowmixer.py     # Unit tests
├── lowwave_cache/           # Audio file caching directory
└── README.md

```

---

## 🚀 Installation & Running

### 1. Install Dependencies

```bash
uv sunc
```

### 2. Create the .env File

Create a `.env` file and add the following configuration:

```bash
# Local LLM configuration
LLM_PATH=./models/your_model_path_here
```

### 3. Run the Project

Launch the main management file (`LowWaveManager`):

```bash
uv run ./main
```

After startup:

* The web server will start in the main thread at `http://localhost:8000`.
* The audio stream (including the looped Rickroll) will be available for listening and client connections at:
`http://localhost:8000/stream`

---

## 🧪 Running Tests

To verify the correct operation of the mixer, queues, and hooks, run `pytest`:

```bash
pytest tests/
```