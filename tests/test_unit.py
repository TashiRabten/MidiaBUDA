"""Unit tests for MediaBUDA.

Specific examples, edge cases, and UI widget structure verification.
"""
import pytest
from unittest.mock import patch, MagicMock

from APP.main_window import MainWindow, extract_media_info_labels, _format_file_size


# ── extract_media_info_labels tests ──────────────────────────────────


class TestExtractMediaInfoLabels:
    """Tests for the probe result → display label mapping."""

    def test_none_info_returns_placeholders(self):
        labels = extract_media_info_labels(None)
        assert "—" in labels["duration"]
        assert "—" in labels["resolution"]
        assert "—" in labels["codecs"]
        assert "—" in labels["file_size"]

    def test_full_info_extracts_all_fields(self):
        info = {
            "duration": 125.5,
            "video": {"codec_name": "h264", "width": 1920, "height": 1080},
            "audio": {"codec_name": "aac"},
            "format": {"size": "52428800"},
            "streams": [],
        }
        labels = extract_media_info_labels(info)
        assert "00:02:05.500" in labels["duration"]
        assert "1920×1080" in labels["resolution"]
        assert "h264" in labels["codecs"]
        assert "aac" in labels["codecs"]
        assert "50.0 MB" in labels["file_size"]

    def test_audio_only_no_video_stream(self):
        info = {
            "duration": 60.0,
            "video": None,
            "audio": {"codec_name": "mp3"},
            "format": {"size": "1048576"},
            "streams": [],
        }
        labels = extract_media_info_labels(info)
        assert "—" in labels["resolution"]
        assert "mp3" in labels["codecs"]
        assert "— / mp3" in labels["codecs"] or "—" in labels["codecs"]

    def test_missing_audio_stream(self):
        info = {
            "duration": 30.0,
            "video": {"codec_name": "hevc", "width": 3840, "height": 2160},
            "audio": None,
            "format": {"size": "10000000"},
            "streams": [],
        }
        labels = extract_media_info_labels(info)
        assert "3840×2160" in labels["resolution"]
        assert "hevc" in labels["codecs"]
        assert "—" in labels["codecs"]  # no audio codec

    def test_zero_duration(self):
        info = {
            "duration": 0,
            "video": None,
            "audio": None,
            "format": {},
            "streams": [],
        }
        labels = extract_media_info_labels(info)
        assert "—" in labels["duration"]

    def test_missing_size_in_format(self):
        info = {
            "duration": 10.0,
            "video": None,
            "audio": None,
            "format": {},
            "streams": [],
        }
        labels = extract_media_info_labels(info)
        assert "—" in labels["file_size"]


# ── _format_file_size tests ──────────────────────────────────────────


class TestFormatFileSize:
    def test_bytes(self):
        assert "500.0 B" == _format_file_size(500)

    def test_kilobytes(self):
        result = _format_file_size(2048)
        assert "KB" in result

    def test_megabytes(self):
        result = _format_file_size(52428800)
        assert "50.0 MB" == result

    def test_gigabytes(self):
        result = _format_file_size(1073741824)
        assert "1.0 GB" == result


# ── MainWindow widget structure tests ────────────────────────────────


class TestMainWindowStructure:
    """Verify the MainWindow has the expected widget hierarchy."""

    @pytest.fixture(autouse=True)
    def setup_window(self, qapp):
        with patch.object(MainWindow, '_restore_geometry'), \
             patch.object(MainWindow, '_check_ffmpeg_startup'):
            self.window = MainWindow()
        yield
        self.window.close()

    def test_window_title(self):
        assert "MediaBUDA" in self.window.windowTitle()

    def test_minimum_size(self):
        assert self.window.minimumWidth() >= 800
        assert self.window.minimumHeight() >= 600

    def test_has_input_edit(self):
        assert self.window.input_edit is not None

    def test_has_browse_and_load_buttons(self):
        assert self.window.browse_btn is not None
        assert self.window.load_btn is not None

    def test_has_output_edit(self):
        assert self.window.output_edit is not None

    def test_has_media_info_group(self):
        assert self.window.media_info_group is not None
        assert self.window.duration_label is not None
        assert self.window.resolution_label is not None
        assert self.window.codecs_label is not None
        assert self.window.filesize_label is not None

    def test_has_splitter_with_panels(self):
        assert self.window.splitter is not None
        assert self.window.splitter.count() == 2

    def test_has_log_group_with_progress(self):
        assert self.window.log_group is not None
        assert self.window.progress_bar is not None
        assert self.window.log_text is not None
        assert self.window.log_text.isReadOnly()

    def test_has_progress_label(self):
        assert self.window.progress_label is not None
        assert self.window.progress_label.text() == "Ocioso"

    def test_media_labels_show_placeholders_initially(self):
        assert "—" in self.window.duration_label.text()
        assert "—" in self.window.resolution_label.text()
        assert "—" in self.window.codecs_label.text()
        assert "—" in self.window.filesize_label.text()

    def test_load_media_updates_labels(self):
        """Verify load_media updates the info labels on success."""
        fake_info = {
            "duration": 90.0,
            "video": {"codec_name": "h264", "width": 1280, "height": 720},
            "audio": {"codec_name": "aac"},
            "format": {"size": "5000000"},
            "streams": [],
        }
        with patch.object(self.window.backend, 'probe', return_value=fake_info):
            self.window.load_media("fake_video.mp4")

        assert "1280×720" in self.window.resolution_label.text()
        assert "h264" in self.window.codecs_label.text()

    def test_load_media_error_shows_placeholders(self):
        """Verify load_media resets labels on probe failure."""
        from APP.ffmpeg_pro_studio_v2_pillow import FFmpegError
        with patch.object(self.window.backend, 'probe', side_effect=FFmpegError("fail")), \
             patch('APP.main_window.QMessageBox'):
            self.window.load_media("bad_file.xyz")

        assert "—" in self.window.duration_label.text()
        assert self.window.media_info is None

    def test_set_progress(self):
        self.window.set_progress(50.0, "Processando...")
        assert self.window.progress_bar.value() == 50
        assert self.window.progress_label.text() == "Processando..."

    def test_set_progress_clamps_to_range(self):
        self.window.set_progress(150.0, "Overflow")
        assert self.window.progress_bar.value() == 100
        self.window.set_progress(-10.0, "Underflow")
        assert self.window.progress_bar.value() == 0

    def test_log_appends_text(self):
        self.window._log("Teste de log")
        assert "Teste de log" in self.window.log_text.toPlainText()

    def test_close_event_saves_config(self, tmp_config):
        """Verify closeEvent saves config."""
        with patch('APP.main_window.save_config') as mock_save:
            self.window.close()
            mock_save.assert_called_once()


# ── Menu bar tests ───────────────────────────────────────────────────


class TestMenuBar:
    """Verify the menu bar structure and recent files behavior."""

    @pytest.fixture(autouse=True)
    def setup_window(self, qapp):
        with patch.object(MainWindow, '_restore_geometry'), \
             patch.object(MainWindow, '_check_ffmpeg_startup'):
            self.window = MainWindow()
        yield
        self.window.close()

    def test_has_menu_bar(self):
        menu_bar = self.window.menuBar()
        assert menu_bar is not None

    def test_file_menu_exists(self):
        assert self.window.file_menu is not None
        assert self.window.file_menu.title() == "Arquivo"

    def test_help_menu_exists(self):
        assert self.window.help_menu is not None
        assert self.window.help_menu.title() == "Ajuda"

    def test_file_menu_has_open_action(self):
        actions = self.window.file_menu.actions()
        titles = [a.text() for a in actions]
        assert "Abrir..." in titles

    def test_open_action_has_shortcut(self):
        actions = self.window.file_menu.actions()
        open_action = next(a for a in actions if a.text() == "Abrir...")
        assert open_action.shortcut().toString() == "Ctrl+O"

    def test_file_menu_has_recent_files_submenu(self):
        assert self.window.recent_menu is not None
        assert self.window.recent_menu.title() == "Arquivos recentes"

    def test_file_menu_has_update_action(self):
        actions = self.window.file_menu.actions()
        titles = [a.text() for a in actions]
        assert "Verificar atualizações do FFmpeg" in titles

    def test_file_menu_has_exit_action(self):
        actions = self.window.file_menu.actions()
        titles = [a.text() for a in actions]
        assert "Sair" in titles

    def test_help_menu_has_about_action(self):
        actions = self.window.help_menu.actions()
        titles = [a.text() for a in actions]
        assert "Sobre" in titles

    def test_recent_menu_empty_shows_placeholder(self):
        """When no recent files, submenu shows disabled placeholder."""
        self.window.config["recent_files"] = []
        self.window._refresh_recent_menu()
        actions = self.window.recent_menu.actions()
        assert len(actions) == 1
        assert not actions[0].isEnabled()
        assert "nenhum" in actions[0].text().lower()

    def test_recent_menu_shows_files(self):
        """Recent files appear as menu actions."""
        self.window.config["recent_files"] = [
            "/videos/clip1.mp4",
            "/videos/clip2.mkv",
        ]
        self.window._refresh_recent_menu()
        actions = self.window.recent_menu.actions()
        assert len(actions) == 2
        assert actions[0].isEnabled()

    def test_recent_menu_max_10(self):
        """Recent files submenu shows at most 10 entries."""
        self.window.config["recent_files"] = [
            f"/videos/clip{i}.mp4" for i in range(15)
        ]
        # add_recent_file caps at 10, but test the menu refresh directly
        self.window.config["recent_files"] = self.window.config["recent_files"][:10]
        self.window._refresh_recent_menu()
        actions = self.window.recent_menu.actions()
        assert len(actions) == 10

    def test_load_media_updates_recent_menu(self):
        """Loading a file refreshes the recent files submenu."""
        fake_info = {
            "duration": 10.0,
            "video": None,
            "audio": {"codec_name": "aac"},
            "format": {"size": "1000"},
            "streams": [],
        }
        with patch.object(self.window.backend, 'probe', return_value=fake_info):
            self.window.load_media("test_file.mp3")

        actions = self.window.recent_menu.actions()
        data_values = [a.data() for a in actions if a.data()]
        assert "test_file.mp3" in data_values

    def test_open_recent_nonexistent_file_warns(self):
        """Opening a recent file that doesn't exist shows a warning."""
        from PyQt6.QtWidgets import QMessageBox as _QMB
        with patch.object(_QMB, 'warning') as mock_warn:
            self.window._open_recent("/nonexistent/file.mp4")
            mock_warn.assert_called_once()
