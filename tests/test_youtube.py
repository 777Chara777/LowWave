import os
import unittest
from unittest.mock import patch, MagicMock
from src.utils.youtube import LowWavePlayerService

class TestLowWavePlayerService(unittest.TestCase):
    
    def setUp(self):
        """Инициализация перед каждым тестом с временной папкой кэша"""
        self.test_cache_dir = "./test_lowwave_cache"
        self.auth = ".envs/oauth.json"
        self.player = LowWavePlayerService(cache_dir=self.test_cache_dir, auth=self.auth)

    def tearDown(self):
        """Очистка временных файлов и папки после тестов"""
        if os.path.exists(self.test_cache_dir):
            for f in os.listdir(self.test_cache_dir):
                try:
                    os.remove(os.path.join(self.test_cache_dir, f))
                except OSError:
                    pass
            try:
                os.rmdir(self.test_cache_dir)
            except OSError:
                pass

    @patch("src.utils.youtube.YTMusic")
    def test_search_track_success(self, mock_ytmusic_class):
        """Проверка успешного поиска трека через YTMusic"""
        mock_yt_instance = mock_ytmusic_class.return_value
        # Исправлено: videoId заменен на ожидаемый в assertions
        mock_yt_instance.search.return_value = [{
            "videoId": "lYBUbBu4W08",
            "title": "Never Gonna Give You Up",
            "artists": [{"name": "Rick Astley"}],
            "album": {"name": "Whenever You Need Somebody"},
            "duration": "3:32",
            "thumbnails": []
        }]

        result = self.player.search_track("Rick Astley")

        self.assertIsNotNone(result)
        if not result: return
        self.assertEqual(result["video_id"], "lYBUbBu4W08")
        self.assertEqual(result["title"], "Never Gonna Give You Up")
        self.assertEqual(result["artists"], "Rick Astley")

    @patch("src.utils.youtube.YTMusic")
    def test_search_track_empty(self, mock_ytmusic_class):
        """Проверка поиска, когда результаты пусты"""
        mock_yt_instance = mock_ytmusic_class.return_value
        mock_yt_instance.search.return_value = []

        result = self.player.search_track("NonexistentTrack12345")
        self.assertIsNone(result)

    @patch("src.utils.youtube.YTMusic")
    def test_get_playlist_tracks(self, mock_ytmusic_class):
        """Проверка получения списка треков из плейлиста"""
        # Настраиваем мок-объект, чтобы он возвращал фейковые данные, а не шел в реальный интернет
        mock_yt_instance = mock_ytmusic_class.return_value
        mock_yt_instance.get_playlist.return_value = {
            "tracks": [{
                "videoId": "abc123xyz",
                "title": "Test Track",
                "artists": [{"name": "Test Artist"}],
                "duration": "2:30"
            }]
        }

        tracks = self.player.get_playlist_tracks("PL123456789")

        self.assertEqual(len(tracks), 1)
        self.assertEqual(tracks[0]["video_id"], "abc123xyz")
        self.assertEqual(tracks[0]["title"], "Test Track")
        self.assertEqual(tracks[0]["artists"], "Test Artist")

        # print("МОК ПОЛУЧЕН:", mock_ytmusic_class)
        # tracks = self.player.get_playlist_tracks("PL123456789")
        # print("БЫЛ ЛИ ВЫЗОВ МОКА:", mock_ytmusic_class.called)

    @patch("src.utils.youtube.yt_dlp.YoutubeDL")
    def test_get_streaming_url(self, mock_ydl_class):
        """Проверка получения прямой ссылки на стриминг"""
        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = {
            "url": "https://rr5---sn-5hneznzsr.googlevideo.com/videoplayback?expire=..."
        }
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

        url = self.player.get_streaming_url("dQw4w9WgXcQ")

        self.assertIsNotNone(url)
        if not url: return
        self.assertTrue(url.startswith("https://"))

    @patch("src.utils.youtube.yt_dlp.YoutubeDL")
    def test_prefetch_track_to_cache(self, mock_ydl_class):
        """Проверка предзагрузки трека в локальный кэш"""
        dummy_filename = os.path.join(self.test_cache_dir, "dQw4w9WgXcQ.m4a")
        
        with open(dummy_filename, "w") as f:
            f.write("fake audio data content")

        mock_ydl_instance = MagicMock()
        mock_ydl_instance.extract_info.return_value = {"id": "dQw4w9WgXcQ", "ext": "m4a"}
        mock_ydl_instance.prepare_filename.return_value = dummy_filename
        mock_ydl_class.return_value.__enter__.return_value = mock_ydl_instance

        file_path = self.player.prefetch_track_to_cache("dQw4w9WgXcQ")

        self.assertEqual(file_path, dummy_filename)
        if not file_path: return
        self.assertTrue(os.path.exists(file_path))

    def test_cleanup_cache(self):
        """Проверка очистки кэша от старых файлов"""
        active_id = "active_id"
        old_id = "old_id"

        file_active = os.path.join(self.test_cache_dir, f"{active_id}.m4a")
        file_old = os.path.join(self.test_cache_dir, f"{old_id}.m4a")

        with open(file_active, "w") as f:
            f.write("active data")
        with open(file_old, "w") as f:
            f.write("old data")

        self.assertTrue(os.path.exists(file_active))
        self.assertTrue(os.path.exists(file_old))

        self.player.cleanup_cache(active_video_id=active_id)

        self.assertTrue(os.path.exists(file_active), "Активный файл должен остаться")
        self.assertFalse(os.path.exists(file_old), "Старый файл должен быть удален")

    @patch("src.utils.youtube.YTMusic")
    def test_service_initialization_with_auth(self, mock_ytmusic_class):
        """Проверка, что параметр auth корректно передается в YTMusic"""
        auth_path = "test_oauth.json"
        
        # Создаем сервис с указанием файла авторизации
        service = LowWavePlayerService(auth=auth_path)
        
        # Обращаемся к ленивому свойству .yt, чтобы инициировать вызов YTMusic
        _ = service.yt
        
        # Проверяем, что класс YTMusic был вызван именно с нашим путем к авторизации
        mock_ytmusic_class.assert_called_once_with(auth_path)

if __name__ == "__main__":
    unittest.main()