import os
import unittest
from src.utils.youtube import LowWavePlayerService

class TestLowWavePlayerIntegration(unittest.TestCase):
    
    def setUp(self):
        """
        Инициализация сервиса. 
        Если у вас есть файл авторизации (например, ".envs/oauth.json"), 
        можете передать его: LowWavePlayerService(auth=".envs/oauth.json")
        """
        self.auth_path = ".envs/oauth.json"
        # Проверяем, есть ли файл авторизации, чтобы запускать тесты с личными плейлистами при наличии
        auth = self.auth_path if os.path.exists(self.auth_path) else None
        self.player = LowWavePlayerService(cache_dir="./integration_cache", auth=auth)

    def test_real_playlist_loading(self):
        """Интеграционный тест: загрузка треков из публичного плейлиста с метаданными"""
        # Используем известный публичный плейлист YouTube Music (например, официальный чарт или плейлист)
        # Либо вы можете подставить ID своего плейлиста
        playlist_id = "PL4fGSI1pDJn6O1LS0XSdF3RyO0Rq_LDeI"
        
        tracks = self.player.get_playlist_tracks_with_meta(playlist_id, limit=5)
        
        # Проверяем, что метод вернул результат и это список
        self.assertIsInstance(tracks, list)
        self.assertGreater(len(tracks), 0, "Плейлист не должен быть пустым")
        
        # Проверяем структуру первого трека
        first_track = tracks[0]
        self.assertIn("video_id", first_track)
        self.assertIn("title", first_track)
        self.assertIn("artists", first_track)
        self.assertIsNotNone(first_track["video_id"])
        
        print(f"\n[Успешно] Загружено треков из плейлиста: {len(tracks)}")
        print(f"Первый трек: {first_track['artists']} — {first_track['title']} ({first_track['video_id']})")

    def tearDown(self):
        """Очистка временного кэша интеграционных тестов"""
        if os.path.exists(self.player.cache_dir):
            for f in os.listdir(self.player.cache_dir):
                try:
                    os.remove(os.path.join(self.player.cache_dir, f))
                except OSError:
                    pass
            try:
                os.rmdir(self.player.cache_dir)
            except OSError:
                pass

if __name__ == "__main__":
    unittest.main()